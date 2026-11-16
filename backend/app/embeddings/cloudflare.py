"""Embedder sobre Cloudflare Workers AI (@cf/baai/bge-m3) vía REST con httpx."""

import time
from collections.abc import Callable, Iterator

import httpx

from app.embeddings.base import DIMENSIONES, EmbeddingError

API_URL = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
REINTENTABLES = {429, 500, 502, 503, 504}


def trocear(items: list[str], tamano: int) -> Iterator[list[str]]:
    """Divide una lista en lotes de como máximo `tamano` elementos."""
    if tamano < 1:
        raise ValueError("tamano debe ser >= 1")
    for i in range(0, len(items), tamano):
        yield items[i : i + tamano]


class CloudflareEmbedder:
    def __init__(
        self,
        account_id: str,
        api_token: str,
        model: str = "@cf/baai/bge-m3",
        *,
        batch_size: int = 32,
        max_retries: int = 5,
        backoff_base: float = 1.0,
        timeout: float = 60.0,
        dimensiones: int = DIMENSIONES,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.model = model
        self._url = API_URL.format(account_id=account_id, model=model)
        self._headers = {"Authorization": f"Bearer {api_token}"}
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._dimensiones = dimensiones
        self._client = client or httpx.Client(timeout=timeout)
        self._sleep = sleep

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        vectores: list[list[float]] = []
        for lote in trocear(textos, self._batch_size):
            vectores.extend(self._embed_lote(lote))
        return vectores

    def embed_query(self, texto: str) -> list[float]:
        return self._embed_lote([texto])[0]

    def _embed_lote(self, lote: list[str]) -> list[list[float]]:
        respuesta = self._post(lote)
        return self._extraer(respuesta, len(lote))

    def _post(self, lote: list[str]) -> httpx.Response:
        """POST con reintentos y backoff exponencial ante 429/5xx y errores de red."""
        ultimo_error = ""
        for intento in range(self._max_retries + 1):
            try:
                r = self._client.post(self._url, json={"text": lote}, headers=self._headers)
            except httpx.TransportError as e:  # timeout, conexión rota, DNS...
                ultimo_error = type(e).__name__
            else:
                if r.status_code < 400:
                    return r
                if r.status_code not in REINTENTABLES:
                    raise EmbeddingError(f"Cloudflare respondió {r.status_code}: {r.text[:200]}")
                ultimo_error = f"HTTP {r.status_code}"
                espera = self._espera_servidor(r)
                if espera is not None and intento < self._max_retries:
                    self._sleep(espera)
                    continue
            if intento < self._max_retries:
                self._sleep(self._backoff_base * 2**intento)
        raise EmbeddingError(
            f"Cloudflare falló tras {self._max_retries + 1} intentos (último: {ultimo_error})"
        )

    @staticmethod
    def _espera_servidor(r: httpx.Response) -> float | None:
        valor = r.headers.get("Retry-After")
        try:
            return min(float(valor), 60.0) if valor is not None else None
        except ValueError:
            return None

    def _extraer(self, r: httpx.Response, esperados: int) -> list[list[float]]:
        try:
            cuerpo = r.json()
        except ValueError as e:
            raise EmbeddingError("Respuesta de Cloudflare no es JSON") from e
        resultado = cuerpo.get("result") if isinstance(cuerpo, dict) else None
        if not isinstance(resultado, dict):
            raise EmbeddingError("Respuesta de Cloudflare sin 'result'")
        # El esquema de salida no está documentado: 'data' es lo habitual; 'response' es respaldo.
        vectores = resultado.get("data") or resultado.get("response")
        if not isinstance(vectores, list) or len(vectores) != esperados:
            raise EmbeddingError(f"Se esperaban {esperados} vectores en la respuesta")
        for v in vectores:
            if not isinstance(v, list) or len(v) != self._dimensiones:
                raise EmbeddingError(f"Se esperaban vectores de {self._dimensiones} dimensiones")
        return vectores
