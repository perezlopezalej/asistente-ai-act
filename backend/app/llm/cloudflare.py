"""LLM sobre Cloudflare Workers AI (por defecto @cf/openai/gpt-oss-120b) vía REST con httpx.

La documentación de gpt-oss en Workers AI no es concluyente sobre el formato exacto de
petición/respuesta (ver ADR 003), así que la petición se construye en `_cuerpo()` y la
respuesta se lee con `_extraer()`, que acepta las formas conocidas. Si la primera ejecución
real difiere, solo hay que tocar esas dos funciones.
"""

import json
import logging
from typing import Any

import httpx

from app.llm.base import LLMCuotaError, LLMError, LLMTruncadoError, RespuestaLLM

log = logging.getLogger(__name__)

API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
CODIGO_CUOTA_AGOTADA = 4006  # "you have used up your daily free allocation of neurons"

# Neuronas por millón de tokens (entrada, salida), según la página de precios de Workers AI.
PRECIOS_NEURONAS: dict[str, tuple[float, float]] = {
    "@cf/openai/gpt-oss-120b": (31_818, 68_182),
    "@cf/openai/gpt-oss-20b": (18_182, 27_273),
}


def neuronas_estimadas(
    modelo: str, tokens_entrada: int | None, tokens_salida: int | None
) -> float | None:
    """Neuronas consumidas según los tokens que devolvió la API (None si no se pueden calcular)."""
    precios = PRECIOS_NEURONAS.get(modelo)
    if precios is None or tokens_entrada is None or tokens_salida is None:
        return None
    return (tokens_entrada * precios[0] + tokens_salida * precios[1]) / 1_000_000


class CloudflareLLM:
    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = "@cf/openai/gpt-oss-120b",
        *,
        max_tokens: int = 3000,
        temperature: float = 0.1,
        reasoning_effort: str = "low",
        timeout: float = 90.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self._url = API_URL.format(account_id=account_id, model=model)
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._client = client or httpx.Client(timeout=timeout)
        # Resumen de la última respuesta (sin contenido ni secretos) para `preguntar.py --debug`.
        self.diagnostico: dict[str, Any] = {}

    def generar(self, system: str, usuario: str, esquema: dict[str, Any]) -> RespuestaLLM:
        peticion = self._cuerpo(system, usuario, esquema)
        self.diagnostico = {"reasoning_effort_enviado": peticion.get("reasoning_effort")}
        try:
            r = self._client.post(self._url, json=peticion, headers=self._headers)
        except httpx.TransportError as e:  # timeout, conexión rota, DNS...
            raise LLMError(f"No se pudo contactar con Cloudflare ({type(e).__name__})") from None
        cuerpo = self._json(r)
        self._comprobar_estado(r, cuerpo)
        resultado = cuerpo.get("result") if isinstance(cuerpo, dict) else None
        if not isinstance(resultado, dict):
            raise LLMError("Respuesta de Cloudflare sin 'result'")
        entrada, salida = self._uso(resultado)
        # Antes de extraer: sirve si falla.
        self.diagnostico |= self._diagnosticar(resultado)
        if self.diagnostico["finish"].get("choices[0].finish_reason") == "length":
            log.warning("respuesta truncada por max_tokens (max_tokens=%d)", self._max_tokens)
            raise LLMTruncadoError("Respuesta truncada por max_tokens: sube LLM_MAX_TOKENS")
        texto, ruta = self._extraer_con_ruta(resultado)
        self.diagnostico["ruta"] = ruta
        return RespuestaLLM(texto, entrada, salida)

    def _cuerpo(self, system: str, usuario: str, esquema: dict[str, Any]) -> dict[str, Any]:
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": usuario},
            ],
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "reasoning_effort": self._reasoning_effort,  # formato chat completions (raíz)
            # Los modelos nativos de Workers AI esperan el JSON Schema "pelado",
            # no el envoltorio de OpenAI {name, schema, strict}.
            "response_format": {"type": "json_schema", "json_schema": esquema},
        }

    @staticmethod
    def _json(r: httpx.Response) -> Any:
        try:
            return r.json()
        except ValueError:
            return None

    @staticmethod
    def _comprobar_estado(r: httpx.Response, cuerpo: Any) -> None:
        errores = cuerpo.get("errors") if isinstance(cuerpo, dict) else None
        codigos = {e.get("code") for e in errores or [] if isinstance(e, dict)}
        if r.status_code == 429 or CODIGO_CUOTA_AGOTADA in codigos:
            raise LLMCuotaError(f"Cloudflare: límite o cuota agotados (HTTP {r.status_code})")
        if r.status_code >= 400:
            detalle = ""
            if errores:
                detalle = "; ".join(
                    str(e.get("message", ""))[:150] for e in errores if isinstance(e, dict)
                )
            raise LLMError(f"Cloudflare respondió {r.status_code}: {detalle or r.text[:150]}")
        if isinstance(cuerpo, dict) and cuerpo.get("success") is False:
            raise LLMError("Cloudflare indicó success=false")

    @classmethod
    def _extraer(cls, resultado: dict[str, Any]) -> str:
        """Devuelve el texto generado, sea cual sea la forma conocida de la respuesta."""
        return cls._extraer_con_ruta(resultado)[0]

    @staticmethod
    def _extraer_con_ruta(resultado: dict[str, Any]) -> tuple[str, str]:
        """Como `_extraer`, y además indica de qué ruta salió el texto."""
        # 1) Chat Completions: choices[0].message.content
        choices = resultado.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            contenido = (choices[0].get("message") or {}).get("content")
            if isinstance(contenido, str) and contenido.strip():
                return contenido, "choices"
        # 2) Responses API: output[] con ítems "message" -> partes "output_text"
        salida = resultado.get("output")
        if isinstance(salida, list):
            trozos = [
                parte["text"]
                for item in salida
                if isinstance(item, dict) and item.get("type") == "message"
                for parte in item.get("content") or []
                if isinstance(parte, dict)
                and parte.get("type") == "output_text"
                and isinstance(parte.get("text"), str)
            ]
            if trozos:
                return "".join(trozos), "output"
        # 3) Atajo de la Responses API
        if isinstance(resultado.get("output_text"), str) and resultado["output_text"].strip():
            return resultado["output_text"], "output_text"
        # 4) {"response": ...}: texto, o objeto ya parseado (lo que devuelve el modo JSON)
        respuesta = resultado.get("response")
        if isinstance(respuesta, str) and respuesta.strip():
            return respuesta, "response (texto)"
        if isinstance(respuesta, dict | list):
            return json.dumps(respuesta, ensure_ascii=False), "response (objeto)"
        # Solo las claves, nunca el contenido: sirve para diagnosticar sin filtrar datos.
        raise LLMError(
            f"Formato de respuesta de Cloudflare no reconocido; claves: {sorted(resultado.keys())}"
        )

    @staticmethod
    def _uso(resultado: dict[str, Any]) -> tuple[int | None, int | None]:
        uso = resultado.get("usage")
        if not isinstance(uso, dict):
            return None, None

        def entero(*claves: str) -> int | None:
            for clave in claves:
                if isinstance(uso.get(clave), int):
                    return uso[clave]
            return None

        return entero("prompt_tokens", "input_tokens"), entero("completion_tokens", "output_tokens")

    @staticmethod
    def _diagnosticar(resultado: dict[str, Any]) -> dict[str, Any]:
        """Datos estructurales de la respuesta: claves, finish_reason/status, usage numérico y
        longitud (no contenido) de los ítems de razonamiento. Nunca texto, token ni URLs."""
        diag: dict[str, Any] = {"claves": sorted(resultado.keys())}
        finish: dict[str, Any] = {}
        choices = resultado.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish["choices[0].finish_reason"] = choices[0].get("finish_reason")
            mensaje = choices[0].get("message") or {}
            razon = mensaje.get("reasoning_content") or mensaje.get("reasoning")
            if isinstance(razon, str):
                diag["razonamiento_chars"] = len(razon)
        if "status" in resultado:
            finish["status"] = resultado["status"]
        if isinstance(resultado.get("incomplete_details"), dict):
            finish["incomplete_details"] = resultado["incomplete_details"]
        salida = resultado.get("output")
        if isinstance(salida, list):
            diag["output_items"] = [
                f"{i.get('type')}:{i.get('status')}" for i in salida if isinstance(i, dict)
            ]
            chars = 0
            for item in salida:
                if isinstance(item, dict) and item.get("type") == "reasoning":
                    for lista in (item.get("content"), item.get("summary")):
                        for parte in lista or []:
                            if isinstance(parte, dict) and isinstance(parte.get("text"), str):
                                chars += len(parte["text"])
            if chars or any(isinstance(i, dict) and i.get("type") == "reasoning" for i in salida):
                diag["razonamiento_chars"] = chars
        diag["finish"] = finish

        def numeros(d: dict[str, Any], prefijo: str = "") -> dict[str, int]:
            plano: dict[str, int] = {}
            for k, v in d.items():
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    plano[prefijo + k] = v
                elif isinstance(v, dict):
                    plano.update(numeros(v, f"{prefijo}{k}."))
            return plano

        uso = resultado.get("usage")
        diag["usage"] = numeros(uso) if isinstance(uso, dict) else None
        return diag
