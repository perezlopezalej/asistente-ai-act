import json

import pytest

from app.rag.esquema import ESQUEMA_SALIDA, SalidaInvalida, SalidaModelo, parsear_salida

VALIDA = {"sin_informacion": False, "afirmaciones": [{"texto": "Hola", "fragmentos": ["a"]}]}


def test_esquema_pelado_coincide_con_el_modelo_pydantic():
    generado = SalidaModelo.model_json_schema()
    assert set(ESQUEMA_SALIDA["properties"]) == set(generado["properties"])
    assert set(ESQUEMA_SALIDA["required"]) == set(generado["required"])
    item = ESQUEMA_SALIDA["properties"]["afirmaciones"]["items"]
    assert set(item["required"]) == set(generado["$defs"]["Afirmacion"]["required"])


def test_esquema_pelado_no_lleva_envoltorio_openai():
    assert "name" not in ESQUEMA_SALIDA
    assert "strict" not in ESQUEMA_SALIDA
    assert "schema" not in ESQUEMA_SALIDA
    assert "$ref" not in json.dumps(ESQUEMA_SALIDA)


def test_parsea_json_valido():
    assert parsear_salida(json.dumps(VALIDA)).afirmaciones[0].fragmentos == ["a"]


def test_parsea_json_dentro_de_valla_de_codigo():
    assert parsear_salida(f"```json\n{json.dumps(VALIDA)}\n```").sin_informacion is False


def test_parsea_json_con_texto_alrededor():
    assert parsear_salida(f"Aquí va: {json.dumps(VALIDA)} Gracias.").sin_informacion is False


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "no es json",
        "{roto",
        "[]",
        '{"sin_informacion": "false", "afirmaciones": []}',  # bool estricto
        '{"sin_informacion": false}',
        '{"sin_informacion": false, "afirmaciones": [{"texto": "", "fragmentos": []}]}',
        '{"sin_informacion": false, "afirmaciones": [{"texto": "x"}]}',
    ],
)
def test_salida_invalida(texto):
    with pytest.raises(SalidaInvalida):
        parsear_salida(texto)
