"""Test de integración REAL del pipeline (Cloudflare + Neon). Se salta si faltan credenciales."""

import pytest

from app.config import settings

requiere_todo = pytest.mark.skipif(
    not (
        settings.cloudflare_account_id and settings.cloudflare_api_token and settings.database_url
    ),
    reason="Faltan CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN / DATABASE_URL",
)


@requiere_todo
def test_pregunta_real_sobre_practicas_prohibidas_cita_el_articulo_5():
    from app.embeddings.factory import crear_embedder
    from app.llm.factory import crear_llm
    from app.rag.pipeline import Pipeline
    from app.rag.recuperacion import BuscadorPostgres

    pipeline = Pipeline(crear_embedder(max_retries=2), BuscadorPostgres(), crear_llm())
    r = pipeline.responder("¿Qué prácticas de inteligencia artificial están prohibidas?")

    assert r.respuesta.estado == "respondida"
    assert r.respuesta.aviso_legal
    assert r.respuesta.afirmaciones
    assert any(c.id.startswith("art-5") for c in r.respuesta.citas)
    assert all(c.url.startswith("http") for c in r.respuesta.citas)
