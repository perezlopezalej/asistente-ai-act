import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.embeddings import EmbeddingCuotaError, FakeEmbedder
from app.llm import FakeLLM, LLMCuotaError, LLMError, LLMTruncadoError
from app.main import app, get_pipeline
from app.rag.fake import FakeBuscador
from app.rag.pipeline import ConfigRag, Pipeline
from app.rag.recuperacion import Recuperacion
from app.schemas import AVISO_LEGAL, MENSAJE_SIN_INFORMACION, limpiar_pregunta
from tests.helpers import frag, recuperacion_basica, salida

CLAVES_RESPUESTA = {"estado", "afirmaciones", "citas", "mensaje", "aviso_legal", "meta"}


@pytest.fixture
def cliente():
    # SIEMPRE se sustituye get_pipeline: FastAPI resuelve las dependencias antes de devolver
    # un 422, así que sin esto el test dependería de las credenciales del entorno.
    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    yield TestClient(app)
    app.dependency_overrides.clear()


def _usar(llm, recuperacion=None, embedder=None):
    pipeline = Pipeline(
        embedder or FakeEmbedder(dimensiones=8),
        FakeBuscador(recuperacion or recuperacion_basica()),
        llm,
        ConfigRag(),
    )
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    return pipeline


def test_respuesta_respondida_tiene_el_contrato_completo(cliente):
    _usar(FakeLLM([salida(("Se prohíbe X.", ["art-5-ap-1"]))]))
    r = cliente.post("/preguntar", json={"pregunta": "¿Qué se prohíbe?"})
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == CLAVES_RESPUESTA
    assert cuerpo["estado"] == "respondida"
    assert cuerpo["mensaje"] is None
    assert cuerpo["afirmaciones"] == [{"texto": "Se prohíbe X.", "citas": [1]}]
    assert cuerpo["citas"] == [
        {
            "n": 1,
            "id": "art-5-ap-1",
            "cita": "CITA DE art-5-ap-1",
            "tipo": "articulo",
            "url": "https://eur-lex.example/art-5-ap-1",
        }
    ]
    assert cuerpo["aviso_legal"] == AVISO_LEGAL
    assert set(cuerpo["meta"]) == {"modelo", "latencia_ms", "similitud_max"}
    uuid.UUID(r.headers["X-Request-ID"])  # sin cabecera del cliente se genera un uuid4


def test_aviso_legal_siempre_presente_tambien_en_abstencion(cliente):
    _usar(FakeLLM([salida()]), Recuperacion(citables=[frag("art-1", similitud=0.1)]))
    r = cliente.post("/preguntar", json={"pregunta": "¿Receta de paella?"})
    assert r.status_code == 200
    assert r.json()["estado"] == "sin_informacion"
    assert r.json()["afirmaciones"] == []
    assert r.json()["mensaje"] == MENSAJE_SIN_INFORMACION
    assert r.json()["aviso_legal"] == AVISO_LEGAL


def test_x_request_id_valido_del_cliente_se_acepta(cliente):
    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    r = cliente.post("/preguntar", json={"pregunta": "x"}, headers={"X-Request-ID": "abc-123-XYZ"})
    assert r.headers["X-Request-ID"] == "abc-123-XYZ"


@pytest.mark.parametrize("malo", ["a" * 65, "con espacios", "inj\\u00e9ctame", "x;y", "a_b"])
def test_x_request_id_invalido_se_sustituye_por_uuid(cliente, malo):
    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    r = cliente.post("/preguntar", json={"pregunta": "x"}, headers={"X-Request-ID": malo})
    rid = r.headers["X-Request-ID"]
    assert rid != malo
    assert uuid.UUID(rid).version == 4


def test_aviso_legal_lo_pone_el_backend_aunque_el_modelo_lo_intente(cliente):
    _usar(FakeLLM([{**salida(("X.", ["art-5-ap-1"])), "aviso_legal": "Esto es legal 100%"}]))
    r = cliente.post("/preguntar", json={"pregunta": "x"})
    assert r.json()["aviso_legal"] == AVISO_LEGAL


def test_cuota_del_llm_devuelve_503(cliente):
    _usar(FakeLLM([LLMCuotaError("HTTP 429 con token-secreto")]))
    r = cliente.post("/preguntar", json={"pregunta": "x"})
    assert r.status_code == 503
    assert "inténtalo más tarde" in r.json()["detail"]
    assert "secreto" not in r.text


def test_cuota_de_embeddings_devuelve_503(cliente):
    class EmbedderSinCuota(FakeEmbedder):
        def embed_query(self, texto):
            raise EmbeddingCuotaError("429")

    _usar(FakeLLM([salida()]), embedder=EmbedderSinCuota(dimensiones=8))
    assert cliente.post("/preguntar", json={"pregunta": "x"}).status_code == 503


def test_otro_fallo_del_llm_devuelve_502_generico(cliente):
    _usar(FakeLLM([LLMError("Cloudflare respondió 500: Authorization Bearer abc123")]))
    r = cliente.post("/preguntar", json={"pregunta": "x"})
    assert r.status_code == 502
    assert r.json() == {"detail": "No se pudo generar la respuesta."}
    assert "abc123" not in r.text


def test_json_invalido_dos_veces_devuelve_502(cliente):
    llm = FakeLLM(["no json", "tampoco"])
    _usar(llm)
    assert cliente.post("/preguntar", json={"pregunta": "x"}).status_code == 502
    assert len(llm.llamadas) == 2


@pytest.mark.parametrize("pregunta", ["", "   ", "\x00\x07", "a" * 1001])
def test_longitud_invalida_devuelve_422(cliente, pregunta):
    llm = FakeLLM([salida()])
    _usar(llm)
    assert cliente.post("/preguntar", json={"pregunta": pregunta}).status_code == 422
    assert llm.llamadas == []


def test_longitud_maxima_exacta_es_valida(cliente):
    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    assert cliente.post("/preguntar", json={"pregunta": "a" * 1000}).status_code == 200


def test_falta_el_campo_pregunta(cliente):
    assert cliente.post("/preguntar", json={}).status_code == 422


def test_caracteres_de_control_se_eliminan_antes_de_llegar_al_modelo(cliente):
    llm = FakeLLM([salida(("X.", ["art-5-ap-1"]))])
    _usar(llm)
    r = cliente.post("/preguntar", json={"pregunta": "  ¿Qué\x00 es​\n  un   sistema‮?  "})
    assert r.status_code == 200
    assert "<pregunta>\n¿Qué es un sistema?\n</pregunta>" in llm.llamadas[0]["usuario"]


def test_limpiar_pregunta():
    assert limpiar_pregunta("a\tb\r\nc\x1b  d") == "a b c d"


def test_el_log_no_contiene_el_texto_de_la_pregunta(cliente, caplog):
    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    pregunta = "Mi DNI es 12345678Z y quiero saber qué prohíbe el Reglamento"
    with caplog.at_level(logging.INFO):
        cliente.post("/preguntar", json={"pregunta": pregunta})
    registros = "\n".join(r.getMessage() for r in caplog.records)
    assert "12345678Z" not in registros
    assert "DNI" not in registros
    assert f"pregunta_len={len(pregunta)}" in registros
    for campo in (
        "req=",
        "estado=respondida",
        "latencia_ms=",
        "similitud_max=",
        "afirmaciones_descartadas=0",
        "ids_descartados=0",
        "tokens_ent=100",
        "tokens_sal=50",
        "neuronas=",
    ):
        assert campo in registros


def test_el_log_registra_los_descartes(cliente, caplog):
    _usar(FakeLLM([salida(("Mala.", ["art-999"]), ("Buena.", ["art-5-ap-1"]))]))
    with caplog.at_level(logging.INFO):
        cliente.post("/preguntar", json={"pregunta": "x"})
    registros = "\n".join(r.getMessage() for r in caplog.records)
    assert "afirmaciones_descartadas=1" in registros
    assert "ids_descartados=1" in registros


def test_truncado_devuelve_502_generico(cliente):
    _usar(FakeLLM([LLMTruncadoError("respuesta truncada por max_tokens")]))
    r = cliente.post("/preguntar", json={"pregunta": "x"})
    assert r.status_code == 502
    assert r.json() == {"detail": "No se pudo generar la respuesta."}


def test_preguntar_devuelve_mensaje_en_sin_informacion_y_null_en_respondida(cliente):
    _usar(
        FakeLLM([salida(("X.", ["art-5-ap-1"]))]), Recuperacion(citables=[frag("a", similitud=0.1)])
    )
    r = cliente.post("/preguntar", json={"pregunta": "¿Receta de paella?"})
    assert r.json()["mensaje"] == MENSAJE_SIN_INFORMACION
    assert r.json()["afirmaciones"] == []

    _usar(FakeLLM([salida(("X.", ["art-5-ap-1"]))]))
    assert cliente.post("/preguntar", json={"pregunta": "x"}).json()["mensaje"] is None
