import httpx
import pytest

from app.embeddings import CloudflareEmbedder, EmbeddingError
from app.embeddings.cloudflare import trocear

DIM = 4
TOKEN = "token-super-secreto"


def _vectores(n: int) -> dict:
    return {"success": True, "result": {"shape": [n, DIM], "data": [[0.1] * DIM] * n}}


def _embedder(handler, **kw):
    esperas: list[float] = []
    cliente = httpx.Client(transport=httpx.MockTransport(handler))
    e = CloudflareEmbedder(
        "cuenta",
        TOKEN,
        dimensiones=DIM,
        client=cliente,
        sleep=esperas.append,
        **kw,
    )
    return e, esperas


def test_trocear_en_lotes():
    assert list(trocear(list("abcde"), 2)) == [["a", "b"], ["c", "d"], ["e"]]
    assert list(trocear([], 3)) == []


def test_trocear_tamano_invalido():
    with pytest.raises(ValueError):
        list(trocear(["a"], 0))


def test_embed_documents_envia_lotes_y_conserva_el_orden():
    lotes: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        textos = json.loads(request.content)["text"]
        lotes.append(textos)
        return httpx.Response(
            200,
            json={"result": {"data": [[float(t)] * DIM for t in textos]}},
        )

    e, _ = _embedder(handler, batch_size=32)
    textos = [str(i) for i in range(70)]
    vectores = e.embed_documents(textos)

    assert [len(lote) for lote in lotes] == [32, 32, 6]
    assert [v[0] for v in vectores] == [float(i) for i in range(70)]


def test_peticion_correcta_url_cabecera_y_cuerpo():
    vistas: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistas.append(request)
        return httpx.Response(200, json=_vectores(1))

    e, _ = _embedder(handler)
    e.embed_query("hola")

    r = vistas[0]
    assert str(r.url) == (
        "https://api.cloudflare.com/client/v4/accounts/cuenta/ai/run/@cf/baai/bge-m3"
    )
    assert r.headers["Authorization"] == f"Bearer {TOKEN}"
    assert r.method == "POST"


def test_reintenta_ante_429_con_backoff_exponencial():
    respuestas = iter([429, 500, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        estado = next(respuestas)
        return httpx.Response(estado, json=_vectores(1) if estado == 200 else {})

    e, esperas = _embedder(handler, backoff_base=1.0)
    assert len(e.embed_query("x")) == DIM
    assert esperas == [1.0, 2.0]


def test_respeta_retry_after():
    respuestas = iter([429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        if next(respuestas) == 429:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json=_vectores(1))

    e, esperas = _embedder(handler)
    e.embed_query("x")
    assert esperas == [7.0]


def test_reintenta_ante_timeout():
    intentos = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal intentos
        intentos += 1
        if intentos == 1:
            raise httpx.ConnectTimeout("tiempo agotado", request=request)
        return httpx.Response(200, json=_vectores(1))

    e, esperas = _embedder(handler)
    e.embed_query("x")
    assert intentos == 2
    assert len(esperas) == 1


def test_falla_tras_agotar_reintentos_sin_filtrar_el_token():
    llamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal llamadas
        llamadas += 1
        return httpx.Response(503)

    e, esperas = _embedder(handler, max_retries=2)
    with pytest.raises(EmbeddingError) as exc:
        e.embed_query("x")

    assert llamadas == 3  # 1 intento + 2 reintentos
    assert esperas == [1.0, 2.0]
    assert TOKEN not in str(exc.value)


def test_error_4xx_no_se_reintenta():
    llamadas = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal llamadas
        llamadas += 1
        return httpx.Response(401, text="Authentication error")

    e, esperas = _embedder(handler)
    with pytest.raises(EmbeddingError, match="401"):
        e.embed_query("x")
    assert llamadas == 1
    assert esperas == []


def test_respuesta_con_numero_de_vectores_incorrecto():
    e, _ = _embedder(lambda r: httpx.Response(200, json=_vectores(1)))
    with pytest.raises(EmbeddingError, match="2 vectores"):
        e.embed_documents(["a", "b"])


def test_respuesta_con_dimensiones_incorrectas():
    bad = {"result": {"data": [[0.1] * (DIM + 1)]}}
    e, _ = _embedder(lambda r: httpx.Response(200, json=bad))
    with pytest.raises(EmbeddingError, match="dimensiones"):
        e.embed_query("x")


def test_respuesta_sin_result():
    e, _ = _embedder(lambda r: httpx.Response(200, json={"success": False}))
    with pytest.raises(EmbeddingError):
        e.embed_query("x")


def test_acepta_response_como_respaldo_de_data():
    cuerpo = {"result": {"response": [[0.5] * DIM]}}
    e, _ = _embedder(lambda r: httpx.Response(200, json=cuerpo))
    assert e.embed_query("x") == [0.5] * DIM
