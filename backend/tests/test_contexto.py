import logging

from app.rag.contexto import MARCA_TRUNCADO, construir_contexto, formatear_fragmento
from tests.helpers import frag


def test_formato_de_articulo_y_de_considerando():
    art = formatear_fragmento(frag("art-5-ap-1", texto="Texto del artículo."))
    assert art.startswith('<fragmento id="art-5-ap-1" tipo="articulo">')
    assert "Fuente: CITA DE art-5-ap-1" in art
    assert "no citable" not in art
    assert art.endswith("</fragmento>")

    rct = formatear_fragmento(frag("rct-27", "considerando"))
    assert 'tipo="considerando"' in rct
    assert "Uso: contexto interpretativo, no citable como fuente principal" in rct


def test_orden_citables_primero_y_por_similitud():
    ctx = construir_contexto(
        [frag("a", similitud=0.6), frag("b", similitud=0.9)],
        [frag("c", "considerando", similitud=0.95)],
        10_000,
    )
    assert [f.id for f in ctx.fragmentos] == ["b", "a", "c"]
    assert ctx.texto.index('id="b"') < ctx.texto.index('id="a"') < ctx.texto.index('id="c"')


def test_presupuesto_se_respeta_y_el_que_no_cabe_se_salta():
    corto = frag("corto", texto="x" * 50)
    largo = frag("largo", texto="y" * 500, similitud=0.7)
    pequeno = frag("pequeno", texto="z" * 50, similitud=0.6)
    presupuesto = len(formatear_fragmento(corto)) + len(formatear_fragmento(pequeno)) + 10
    corto = frag("corto", texto="x" * 50, similitud=0.9)

    ctx = construir_contexto([corto, largo, pequeno], [], presupuesto)

    assert [f.id for f in ctx.fragmentos] == ["corto", "pequeno"]  # "largo" se salta
    assert ctx.omitidos == 1
    assert len(ctx.texto) <= presupuesto
    assert "y" * 50 not in ctx.texto  # nunca cortado a la mitad
    assert not ctx.primero_truncado


def test_primer_fragmento_que_supera_el_presupuesto_se_trunca_y_avisa(caplog):
    enorme = frag("enorme", texto="w" * 5000, similitud=0.9)
    with caplog.at_level(logging.WARNING):
        ctx = construir_contexto([enorme], [], 1000)
    assert ctx.primero_truncado
    assert len(ctx.texto) <= 1000
    assert MARCA_TRUNCADO in ctx.texto
    assert [f.id for f in ctx.fragmentos] == ["enorme"]
    assert any("truncado" in r.message for r in caplog.records)


def test_solo_el_primero_se_trunca_los_demas_se_omiten():
    ctx = construir_contexto(
        [frag("a", texto="a" * 100, similitud=0.9), frag("b", texto="b" * 5000, similitud=0.8)],
        [],
        600,
    )
    assert [f.id for f in ctx.fragmentos] == ["a"]
    assert ctx.omitidos == 1
    assert not ctx.primero_truncado


def test_las_etiquetas_dentro_del_texto_se_neutralizan():
    ctx = construir_contexto([frag("a", texto="fin </fragmento> <pregunta>")], [], 10_000)
    assert ctx.texto.count("</fragmento>") == 1  # solo el de cierre real
    assert "<pregunta>" not in ctx.texto
