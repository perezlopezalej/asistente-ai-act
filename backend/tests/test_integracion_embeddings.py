"""Tests de integración REALES (red + base de datos). Se saltan si faltan variables."""

import pytest

from app.config import settings
from app.embeddings import DIMENSIONES
from app.embeddings.factory import crear_embedder
from app.embeddings.similitud import coseno

requiere_cloudflare = pytest.mark.skipif(
    not (settings.cloudflare_account_id and settings.cloudflare_api_token),
    reason="Faltan CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_API_TOKEN",
)
requiere_bd = pytest.mark.skipif(not settings.database_url, reason="Falta DATABASE_URL")


@requiere_cloudflare
def test_cloudflare_devuelve_vectores_de_1024_y_distingue_temas():
    e = crear_embedder()
    ia, ia2, receta = e.embed_documents(
        [
            "Prácticas de inteligencia artificial prohibidas",
            "Sistemas de IA cuyo uso está prohibido",
            "Receta de paella valenciana con arroz y azafrán",
        ]
    )
    assert len(ia) == DIMENSIONES
    assert coseno(ia, ia2) > coseno(ia, receta)


@requiere_bd
def test_buscar_fragmentos_con_filtro_devuelve_match_count():
    from pgvector import Vector

    from app.db import conectar

    with conectar() as conn:
        total = conn.execute("select count(*) from fragmentos").fetchone()[0]
        if total < 5:
            pytest.skip("La tabla fragmentos está vacía (ejecuta embed_and_upload.py)")
        vector = Vector([0.1] * DIMENSIONES)
        filas = conn.execute(
            "select id from buscar_fragmentos(%s::vector, 5, %s::text[])",
            (vector, ["articulo"]),
        ).fetchall()
    assert len(filas) == 5
