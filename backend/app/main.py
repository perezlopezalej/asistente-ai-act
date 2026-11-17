import logging
import re
import uuid
from functools import lru_cache
from typing import Annotated

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Response

from app.config import settings
from app.db import DatabaseError
from app.embeddings.base import EmbeddingCuotaError, EmbeddingError
from app.embeddings.factory import crear_embedder
from app.llm.base import LLMCuotaError, LLMError
from app.llm.factory import crear_llm
from app.rag.pipeline import Pipeline
from app.rag.recuperacion import BuscadorPostgres
from app.schemas import PreguntaIn, RespuestaOut

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

log = logging.getLogger("app.api")

app = FastAPI(title="Asistente AI Act")

ID_VALIDO = re.compile(r"[A-Za-z0-9-]{1,64}")
MENSAJE_503 = "Servicio temporalmente no disponible: inténtalo más tarde."
MENSAJE_502 = "No se pudo generar la respuesta."


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache
def get_pipeline() -> Pipeline:
    if not (settings.cloudflare_account_id and settings.cloudflare_api_token):
        raise RuntimeError("Configuración incompleta: faltan credenciales de Cloudflare")
    if not settings.database_url:
        raise RuntimeError("Configuración incompleta: falta DATABASE_URL")
    # Pocos reintentos en el embedder: una petición web no debe esperar ~30 s.
    return Pipeline(crear_embedder(max_retries=2), BuscadorPostgres(), crear_llm())


def _fmt(valor: object) -> str:
    return "n/d" if valor is None else str(valor)


@app.post("/preguntar", response_model=RespuestaOut)
def preguntar(
    entrada: PreguntaIn,
    response: Response,
    pipeline: Annotated[Pipeline, Depends(get_pipeline)],
    x_request_id: Annotated[str | None, Header()] = None,
) -> RespuestaOut:
    # Un id del cliente solo se acepta con formato seguro (evita inyección en logs/cabeceras).
    req_id = (
        x_request_id if x_request_id and ID_VALIDO.fullmatch(x_request_id) else str(uuid.uuid4())
    )
    headers = {"X-Request-ID": req_id}
    response.headers["X-Request-ID"] = req_id
    try:
        resultado = pipeline.responder(entrada.pregunta)
    except (LLMCuotaError, EmbeddingCuotaError) as e:
        # Solo el tipo de error: nunca el texto de la pregunta ni credenciales.
        log.warning("req=%s error=cuota tipo=%s", req_id, type(e).__name__)
        raise HTTPException(503, MENSAJE_503, headers=headers) from None
    except (LLMError, EmbeddingError, DatabaseError, psycopg.Error) as e:
        log.error("req=%s error=proveedor tipo=%s detalle=%s", req_id, type(e).__name__, e)
        raise HTTPException(502, MENSAJE_502, headers=headers) from None

    meta, consumo = resultado.respuesta.meta, resultado.consumo
    # No se registra el texto de la pregunta (puede contener datos personales), solo su longitud.
    log.info(
        "req=%s pregunta_len=%d estado=%s latencia_ms=%d similitud_max=%.3f "
        "afirmaciones_descartadas=%d ids_descartados=%d llamadas_llm=%d "
        "tokens_ent=%s tokens_sal=%s neuronas=%s",
        req_id,
        len(entrada.pregunta),
        resultado.respuesta.estado,
        meta.latencia_ms,
        meta.similitud_max,
        resultado.afirmaciones_descartadas,
        resultado.ids_descartados,
        consumo.llamadas_llm,
        _fmt(consumo.tokens_entrada),
        _fmt(consumo.tokens_salida),
        "n/d" if consumo.neuronas is None else f"{consumo.neuronas:.1f}",
    )
    return resultado.respuesta
