from app.rag.esquema import SalidaModelo
from app.rag.verificacion import verificar_citas
from tests.helpers import frag, salida

ENVIADOS = [
    frag("art-5-ap-1"),
    frag("anx-III-sec-1", "anexo"),
    frag("rct-27", "considerando"),
]


def _verificar(*afirmaciones, sin_informacion=False):
    return verificar_citas(
        SalidaModelo.model_validate(salida(*afirmaciones, sin_informacion=sin_informacion)),
        ENVIADOS,
    )


def test_ids_inventados_se_descartan_y_se_cuentan():
    v = _verificar(("Está prohibido.", ["art-5-ap-1", "art-999"]))
    assert [c.id for c in v.citas] == ["art-5-ap-1"]
    assert v.ids_descartados == 1
    assert v.afirmaciones_descartadas == 0


def test_afirmacion_con_solo_ids_inventados_se_descarta():
    v = _verificar(("Inventado.", ["art-999"]), ("Real.", ["art-5-ap-1"]))
    assert [a.texto for a in v.afirmaciones] == ["Real."]
    assert v.afirmaciones_descartadas == 1
    assert v.ids_descartados == 1


def test_afirmacion_solo_con_considerandos_se_descarta():
    v = _verificar(("Solo contexto.", ["rct-27"]))
    assert v.vacia
    assert v.afirmaciones_descartadas == 1
    assert v.citas == []


def test_considerando_puede_acompanar_a_un_articulo():
    v = _verificar(("Con apoyo.", ["rct-27", "art-5-ap-1"]))
    assert [c.tipo for c in v.citas] == ["considerando", "articulo"]
    assert v.afirmaciones[0].citas == [1, 2]


def test_todo_descartado_deja_la_verificacion_vacia():
    v = _verificar(("A.", ["x"]), ("B.", ["rct-27"]), ("C.", []))
    assert v.vacia
    assert v.afirmaciones_descartadas == 3


def test_numeracion_por_orden_de_aparicion_y_datos_desde_la_bd():
    v = _verificar(
        ("Primera.", ["anx-III-sec-1"]),
        ("Segunda.", ["art-5-ap-1", "anx-III-sec-1"]),
    )
    assert [(c.n, c.id) for c in v.citas] == [(1, "anx-III-sec-1"), (2, "art-5-ap-1")]
    assert v.afirmaciones[0].citas == [1]
    assert v.afirmaciones[1].citas == [1, 2]
    assert v.citas[0].cita == "CITA DE anx-III-sec-1"
    assert v.citas[0].url == "https://eur-lex.example/anx-III-sec-1"
    assert v.citas[0].tipo == "anexo"


def test_ids_duplicados_cuentan_una_vez():
    v = _verificar(("X.", ["art-5-ap-1", "art-5-ap-1"]))
    assert v.afirmaciones[0].citas == [1]
    assert len(v.citas) == 1


def test_se_quitan_marcadores_escritos_por_el_modelo():
    v = _verificar(("Está prohibido [3] y [1, 2].", ["art-5-ap-1"]))
    assert v.afirmaciones[0].texto == "Está prohibido y."


def test_texto_vacio_tras_limpiar_se_descarta():
    v = _verificar(("[1]", ["art-5-ap-1"]))
    assert v.vacia


def test_sin_informacion_del_modelo_ignora_las_afirmaciones():
    v = _verificar(("Algo.", ["art-5-ap-1"]), sin_informacion=True)
    assert v.vacia
    assert v.afirmaciones_descartadas == 0
