import json
from pathlib import Path

import pytest

from app.ingest.parser import parsear

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "mini_ai_act.html"
HTML_COMPLETO = RAIZ / "data" / "raw" / "CELEX_32024R1689_ES_TXT.html"
CHUNKS = RAIZ / "data" / "processed" / "chunks.jsonl"


# --- Fixture mínimo (corre siempre, también en CI) ---


@pytest.fixture(scope="module")
def mini():
    return {f.id: f for f in parsear(FIXTURE)}


def test_mini_ids_esperados(mini):
    assert set(mini) == {
        "rct-1",
        "art-1-ap-1",
        "art-1-ap-2",
        "art-3-ap-1",
        "art-3-ap-2",
        "anx-III-intro",
        "anx-III-p-1",
    }


def test_mini_considerando(mini):
    c = mini["rct-1"]
    assert c.tipo == "considerando"
    assert c.cita == "Considerando 1"
    assert c.texto.startswith("El objetivo del presente Reglamento")


def test_mini_apartados_con_letras(mini):
    ap2 = mini["art-1-ap-2"]
    assert ap2.cita == "Artículo 1, apartado 2"
    assert ap2.titulo_articulo == "Objeto"
    assert ap2.capitulo == "CAPÍTULO I — DISPOSICIONES GENERALES"
    # Las letras quedan dentro del apartado.
    assert "a) normas armonizadas" in ap2.texto
    assert "\xa0" not in ap2.texto


def test_mini_definiciones(mini):
    assert mini["art-3-ap-2"].cita == "Artículo 3, punto 2 («riesgo»)"
    assert mini["art-3-ap-1"].apartado == "1"


def test_mini_anexo(mini):
    p1 = mini["anx-III-p-1"]
    assert p1.tipo == "anexo"
    assert p1.numero == "III"
    assert p1.cita == "Anexo III, punto 1"
    assert "Biometría" in p1.texto
    assert "reconocimiento de emociones" in p1.texto  # letras anidadas


def test_mini_sin_textos_vacios(mini):
    assert all(f.texto.strip() for f in mini.values())


# --- chunks.jsonl versionado ---


@pytest.fixture(scope="module")
def chunks():
    return [json.loads(linea) for linea in CHUNKS.read_text(encoding="utf-8").splitlines()]


def test_chunks_113_articulos(chunks):
    assert len({c["numero"] for c in chunks if c["tipo"] == "articulo"}) == 113


def test_chunks_180_considerandos(chunks):
    assert sum(1 for c in chunks if c["tipo"] == "considerando") == 180


def test_chunks_sin_textos_vacios(chunks):
    assert all(c["texto"].strip() for c in chunks)


def test_chunks_ids_unicos(chunks):
    ids = [c["id"] for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunks_articulo_3_por_definicion(chunks):
    assert sum(1 for c in chunks if c["tipo"] == "articulo" and c["numero"] == "3") == 68


def test_chunks_articulo_5_apartados(chunks):
    aps = [c["apartado"] for c in chunks if c["tipo"] == "articulo" and c["numero"] == "5"]
    assert aps == [str(i) for i in range(1, 9)]


def test_chunks_anexo_iii(chunks):
    assert any(c["tipo"] == "anexo" and c["numero"] == "III" for c in chunks)


# --- HTML completo (solo si está descargado; data/raw no se versiona) ---


@pytest.mark.skipif(not HTML_COMPLETO.exists(), reason="HTML completo no descargado")
def test_html_completo_coincide_con_chunks(chunks):
    assert [json.loads(f.model_dump_json()) for f in parsear(HTML_COMPLETO)] == chunks
