import json

import httpx
import pytest

from app.llm import (
    CloudflareLLM,
    LLMCuotaError,
    LLMError,
    LLMTruncadoError,
    neuronas_estimadas,
)
from app.rag.esquema import ESQUEMA_SALIDA

TOKEN = "token-super-secreto"


def _llm(handler, **kw) -> CloudflareLLM:
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    return CloudflareLLM("cuenta", TOKEN, client=cliente, **kw)


def _ok(resultado: dict):
    return lambda request: httpx.Response(200, json={"success": True, "result": resultado})


def test_peticion_url_cabecera_y_cuerpo():
    vistas: list[httpx.Request] = []

    def handler(request):
        vistas.append(request)
        return httpx.Response(200, json={"result": {"response": '{"a": 1}'}})

    _llm(handler, max_tokens=1000, temperature=0.1).generar("SYS", "USR", ESQUEMA_SALIDA)

    r = vistas[0]
    assert str(r.url) == (
        "https://api.cloudflare.com/client/v4/accounts/cuenta/ai/run/@cf/openai/gpt-oss-120b"
    )
    assert r.method == "POST"
    assert r.headers["Authorization"] == f"Bearer {TOKEN}"
    cuerpo = json.loads(r.content)
    assert cuerpo["messages"] == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "USR"},
    ]
    assert cuerpo["max_tokens"] == 1000
    assert cuerpo["temperature"] == 0.1
    assert cuerpo["reasoning_effort"] == "low"  # raíz, formato chat completions
    assert "reasoning" not in cuerpo
    # Esquema "pelado": sin el envoltorio de OpenAI {name, schema, strict}.
    assert cuerpo["response_format"] == {"type": "json_schema", "json_schema": ESQUEMA_SALIDA}
    assert "strict" not in cuerpo["response_format"]["json_schema"]


@pytest.mark.parametrize(
    "resultado",
    [
        {"choices": [{"message": {"content": "TEXTO"}}]},
        {
            "output": [
                {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "pienso"}]},
                {"type": "message", "content": [{"type": "output_text", "text": "TEXTO"}]},
            ]
        },
        {"output_text": "TEXTO"},
        {"response": "TEXTO"},
    ],
)
def test_extrae_el_texto_en_todas_las_formas_conocidas(resultado):
    assert _llm(_ok(resultado)).generar("s", "u", {}).texto == "TEXTO"


def test_response_ya_parseado_se_serializa_a_json():
    r = _llm(_ok({"response": {"sin_informacion": True, "afirmaciones": []}})).generar("s", "u", {})
    assert json.loads(r.texto) == {"sin_informacion": True, "afirmaciones": []}


def test_ignora_el_razonamiento_y_no_lo_devuelve():
    resultado = {
        "output": [
            {"type": "reasoning", "content": [{"type": "reasoning_text", "text": "secreto"}]}
        ]
    }
    with pytest.raises(LLMError, match="no reconocido"):
        _llm(_ok(resultado)).generar("s", "u", {})


@pytest.mark.parametrize(
    ("uso", "esperado"),
    [
        ({"prompt_tokens": 10, "completion_tokens": 5}, (10, 5)),
        ({"input_tokens": 7, "output_tokens": 3}, (7, 3)),
        (None, (None, None)),
    ],
)
def test_lee_el_uso_de_tokens(uso, esperado):
    resultado = {"response": "x"} | ({"usage": uso} if uso else {})
    r = _llm(_ok(resultado)).generar("s", "u", {})
    assert (r.tokens_entrada, r.tokens_salida) == esperado


def test_formato_no_reconocido_lista_solo_las_claves():
    with pytest.raises(LLMError) as exc:
        _llm(_ok({"algo_raro": "CONTENIDO-PRIVADO"})).generar("s", "u", {})
    assert "algo_raro" in str(exc.value)
    assert "CONTENIDO-PRIVADO" not in str(exc.value)


def test_429_es_error_de_cuota_y_no_se_reintenta():
    llamadas = 0

    def handler(request):
        nonlocal llamadas
        llamadas += 1
        return httpx.Response(429, json={"errors": [{"code": 3040, "message": "rate"}]})

    with pytest.raises(LLMCuotaError):
        _llm(handler).generar("s", "u", {})
    assert llamadas == 1


def test_codigo_4006_es_cuota_agotada_aunque_no_sea_429():
    cuerpo = {"success": False, "errors": [{"code": 4006, "message": "daily allocation"}]}
    with pytest.raises(LLMCuotaError):
        _llm(lambda r: httpx.Response(400, json=cuerpo)).generar("s", "u", {})


def test_error_4xx_es_llmerror_sin_filtrar_el_token():
    with pytest.raises(LLMError) as exc:
        _llm(lambda r: httpx.Response(401, text="Authentication error")).generar("s", "u", {})
    assert not isinstance(exc.value, LLMCuotaError)
    assert "401" in str(exc.value)
    assert TOKEN not in str(exc.value)


def test_error_de_red_es_llmerror_sin_filtrar_el_token():
    def handler(request):
        raise httpx.ConnectTimeout("tiempo agotado", request=request)

    with pytest.raises(LLMError) as exc:
        _llm(handler).generar("s", "u", {})
    assert TOKEN not in str(exc.value)


def test_respuesta_sin_result_o_no_json():
    with pytest.raises(LLMError):
        _llm(lambda r: httpx.Response(200, json={"success": True})).generar("s", "u", {})
    with pytest.raises(LLMError):
        _llm(lambda r: httpx.Response(200, text="<html>")).generar("s", "u", {})


def test_neuronas_estimadas():
    # 1.000 tokens de entrada y 500 de salida con gpt-oss-120b
    esperado = (1000 * 31_818 + 500 * 68_182) / 1_000_000
    assert neuronas_estimadas("@cf/openai/gpt-oss-120b", 1000, 500) == pytest.approx(esperado)
    assert neuronas_estimadas("@cf/openai/gpt-oss-20b", 1000, 500) == pytest.approx(
        (1000 * 18_182 + 500 * 27_273) / 1_000_000
    )
    assert neuronas_estimadas("otro-modelo", 1, 1) is None
    assert neuronas_estimadas("@cf/openai/gpt-oss-120b", None, 5) is None


def test_diagnostico_no_contiene_contenido_ni_secretos():
    resultado = {
        "output": [
            {"type": "reasoning", "status": "completed", "content": [{"text": "x" * 123}]},
            {"type": "message", "content": [{"type": "output_text", "text": "TEXTO-PRIVADO"}]},
        ],
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "usage": {
            "input_tokens": 10,
            "output_tokens": 20,
            "output_tokens_details": {"reasoning_tokens": 15},
        },
    }
    llm = _llm(_ok(resultado))
    llm.generar("s", "u", {})
    d = llm.diagnostico
    assert d["ruta"] == "output"
    assert d["claves"] == ["incomplete_details", "output", "status", "usage"]
    assert d["razonamiento_chars"] == 123
    assert d["finish"]["status"] == "incomplete"
    assert d["usage"] == {
        "input_tokens": 10,
        "output_tokens": 20,
        "output_tokens_details.reasoning_tokens": 15,
    }
    assert "TEXTO-PRIVADO" not in str(d) and TOKEN not in str(d)


def test_diagnostico_disponible_aunque_el_formato_no_se_reconozca():
    llm = _llm(_ok({"rara": 1}))
    with pytest.raises(LLMError):
        llm.generar("s", "u", {})
    assert llm.diagnostico["claves"] == ["rara"]
    assert "ruta" not in llm.diagnostico


def test_finish_reason_length_lanza_error_especifico_y_lo_registra(caplog):
    resultado = {"choices": [{"finish_reason": "length", "message": {"content": '{"sin_inf'}}]}
    llm = _llm(_ok(resultado))
    with caplog.at_level("WARNING"):
        with pytest.raises(LLMTruncadoError, match="truncada por max_tokens"):
            llm.generar("s", "u", {})
    assert any("truncada por max_tokens" in r.message for r in caplog.records)
    assert llm.diagnostico["finish"]["choices[0].finish_reason"] == "length"
    assert llm.diagnostico["reasoning_effort_enviado"] == "low"


def test_finish_reason_stop_no_es_truncado():
    resultado = {"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
    assert _llm(_ok(resultado)).generar("s", "u", {}).texto == "{}"


def test_max_tokens_por_defecto_es_3000():
    from app.config import Settings

    assert Settings.model_fields["llm_max_tokens"].default == 3000
