from app.embeddings import FakeEmbedder, calcular_hash, texto_para_embedding
from app.embeddings.base import DIMENSIONES, Embedder
from app.ingest.parser import Fragmento

URL = "https://eur-lex.europa.eu/legal-content/ES/TXT/HTML/?uri=CELEX:32024R1689"


def _fr(**kw) -> Fragmento:
    base = {"id": "x", "tipo": "articulo", "numero": "5", "texto": "Texto.", "url_fuente": URL}
    return Fragmento(**{**base, **kw})


def test_cabecera_articulo_con_apartado():
    fr = _fr(
        apartado="1",
        titulo_articulo="Prácticas de IA prohibidas",
        cita="Artículo 5, apartado 1",
        texto="Quedan prohibidas las siguientes prácticas de IA:",
    )
    assert texto_para_embedding(fr) == (
        "Artículo 5. Prácticas de IA prohibidas. Apartado 1: "
        "Quedan prohibidas las siguientes prácticas de IA:"
    )


def test_cabecera_articulo_sin_apartado():
    fr = _fr(numero="4", titulo_articulo="Alfabetización en materia de IA", cita="Artículo 4")
    assert texto_para_embedding(fr) == "Artículo 4. Alfabetización en materia de IA: Texto."


def test_cabecera_definicion_art_3_conserva_el_termino():
    fr = _fr(
        numero="3",
        apartado="1",
        titulo_articulo="Definiciones",
        cita="Artículo 3, punto 1 («sistema de IA»)",
    )
    assert texto_para_embedding(fr).startswith(
        "Artículo 3. Definiciones. Punto 1 («sistema de IA»): "
    )


def test_cabecera_considerando():
    fr = _fr(tipo="considerando", numero="3", cita="Considerando 3", texto="Los sistemas de IA…")
    assert texto_para_embedding(fr) == "Considerando 3: Los sistemas de IA…"


def test_cabecera_anexo():
    fr = _fr(
        tipo="anexo",
        numero="III",
        apartado="1",
        titulo_articulo="Sistemas de IA de alto riesgo",
        cita="Anexo III, punto 1",
    )
    assert texto_para_embedding(fr).startswith(
        "Anexo III. Sistemas de IA de alto riesgo. Punto 1: "
    )


def test_el_texto_original_no_se_modifica():
    fr = _fr(cita="Artículo 5, apartado 1", texto="Original")
    texto_para_embedding(fr)
    assert fr.texto == "Original"


def test_hash_estable_y_sensible_a_texto_y_modelo():
    h = calcular_hash("texto", "bge-m3")
    assert h == calcular_hash("texto", "bge-m3")
    assert len(h) == 64
    assert h != calcular_hash("texto distinto", "bge-m3")
    assert h != calcular_hash("texto", "otro-modelo")


def test_hash_no_confunde_la_frontera_texto_modelo():
    assert calcular_hash("ab", "c") != calcular_hash("a", "bc")


def test_fake_embedder_cumple_el_protocolo_y_es_determinista():
    e: Embedder = FakeEmbedder()
    v1, v2 = e.embed_documents(["a", "b"])
    assert len(v1) == DIMENSIONES
    assert v1 != v2
    assert e.embed_query("a") == v1
