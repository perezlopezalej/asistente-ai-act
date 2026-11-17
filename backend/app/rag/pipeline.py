"""Pipeline RAG: pregunta -> recuperación -> abstención -> LLM -> verificación -> respuesta."""

import logging
import time
from dataclasses import dataclass

from app.config import settings
from app.embeddings.base import Embedder
from app.llm.base import LLM, LLMError
from app.llm.cloudflare import neuronas_estimadas
from app.rag.contexto import construir_contexto
from app.rag.esquema import ESQUEMA_SALIDA, SalidaInvalida, SalidaModelo, parsear_salida
from app.rag.prompt import SYSTEM_PROMPT, mensaje_usuario
from app.rag.recuperacion import Buscador
from app.rag.verificacion import verificar_citas
from app.schemas import (
    MENSAJE_SIN_INFORMACION,
    MetaOut,
    RespuestaOut,
)

log = logging.getLogger(__name__)

INTENTOS_LLM = 2  # 1 petición + 1 reintento si la salida no es válida


@dataclass
class ConfigRag:
    umbral_similitud: float = 0.45
    k_articulos: int = 5
    k_considerandos: int = 2
    presupuesto_contexto_caracteres: int = 10000

    @classmethod
    def desde_settings(cls) -> "ConfigRag":
        return cls(
            settings.umbral_similitud,
            settings.k_articulos,
            settings.k_considerandos,
            settings.presupuesto_contexto_caracteres,
        )


@dataclass
class Consumo:
    llamadas_llm: int = 0
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    neuronas: float | None = None


@dataclass
class ResultadoPipeline:
    respuesta: RespuestaOut
    consumo: Consumo
    afirmaciones_descartadas: int = 0
    ids_descartados: int = 0


class Pipeline:
    def __init__(
        self,
        embedder: Embedder,
        buscador: Buscador,
        llm: LLM,
        config: ConfigRag | None = None,
    ) -> None:
        self._embedder = embedder
        self._buscador = buscador
        self._llm = llm
        self._config = config or ConfigRag.desde_settings()

    def responder(self, pregunta: str) -> ResultadoPipeline:
        inicio = time.perf_counter()
        cfg = self._config

        vector = self._embedder.embed_query(pregunta)
        recuperados = self._buscador.buscar(vector, cfg.k_articulos, cfg.k_considerandos)
        similitud_max = recuperados.similitud_max

        # Barrera 1: sin artículo/anexo suficientemente parecido no se llama al LLM.
        if not recuperados.citables or similitud_max < cfg.umbral_similitud:
            log.info(
                "abstención sin LLM: similitud_max=%.3f < umbral=%.2f",
                similitud_max,
                cfg.umbral_similitud,
            )
            return self._abstencion(inicio, similitud_max, Consumo())

        contexto = construir_contexto(
            recuperados.citables, recuperados.considerandos, cfg.presupuesto_contexto_caracteres
        )
        if contexto.omitidos:
            log.info("contexto: %d fragmentos no cupieron en el presupuesto", contexto.omitidos)

        salida, consumo = self._generar(mensaje_usuario(contexto.texto, pregunta))
        # Solo se aceptan ids de los fragmentos que realmente se enviaron al modelo.
        verificacion = verificar_citas(salida, contexto.fragmentos)

        if verificacion.vacia:
            resultado = self._abstencion(inicio, similitud_max, consumo)
        else:
            respuesta = RespuestaOut(
                estado="respondida",
                afirmaciones=verificacion.afirmaciones,
                citas=verificacion.citas,
                meta=self._meta(inicio, similitud_max),
            )
            resultado = ResultadoPipeline(respuesta, consumo)
        resultado.afirmaciones_descartadas = verificacion.afirmaciones_descartadas
        resultado.ids_descartados = verificacion.ids_descartados
        return resultado

    def _generar(self, usuario: str) -> tuple[SalidaModelo, Consumo]:
        consumo = Consumo()
        for intento in range(1, INTENTOS_LLM + 1):
            r = self._llm.generar(SYSTEM_PROMPT, usuario, ESQUEMA_SALIDA)  # LLMError sube tal cual
            consumo.llamadas_llm += 1
            if r.tokens_entrada is not None:
                consumo.tokens_entrada = (consumo.tokens_entrada or 0) + r.tokens_entrada
            if r.tokens_salida is not None:
                consumo.tokens_salida = (consumo.tokens_salida or 0) + r.tokens_salida
            consumo.neuronas = neuronas_estimadas(
                self._llm.model, consumo.tokens_entrada, consumo.tokens_salida
            )
            try:
                return parsear_salida(r.texto), consumo
            except SalidaInvalida as e:
                # Se registra solo el motivo y la longitud: nunca el contenido de la salida.
                log.warning(
                    "salida inválida del modelo (intento %d): %s (len=%d)", intento, e, len(r.texto)
                )
        raise LLMError(f"El modelo no devolvió una salida válida tras {INTENTOS_LLM} intentos")

    def _meta(self, inicio: float, similitud_max: float) -> MetaOut:
        return MetaOut(
            modelo=self._llm.model,
            latencia_ms=round((time.perf_counter() - inicio) * 1000),
            similitud_max=round(similitud_max, 4),
        )

    def _abstencion(
        self, inicio: float, similitud_max: float, consumo: Consumo
    ) -> ResultadoPipeline:
        respuesta = RespuestaOut(
            estado="sin_informacion",
            afirmaciones=[],
            citas=[],
            mensaje=MENSAJE_SIN_INFORMACION,
            meta=self._meta(inicio, similitud_max),
        )
        return ResultadoPipeline(respuesta, consumo)
