"""Tests (sin red ni BD) de las funciones de métricas de `evals/eval_busqueda.py`."""

import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("eval_busqueda", RAIZ / "evals" / "eval_busqueda.py")
eb = importlib.util.module_from_spec(_spec)
sys.modules["eval_busqueda"] = eb
_spec.loader.exec_module(eb)

RANKING = ["a", "b", "c", "d", "e", "f", "g"]


def test_posiciones():
    assert eb.posiciones(["a", "g", "z"], RANKING) == {"a": 1, "g": 7, "z": None}


def test_hit_y_recall():
    assert eb.hit_en_k(["c", "z"], RANKING, 5)
    assert not eb.hit_en_k(["f", "z"], RANKING, 5)
    assert eb.recall_en_k(["a", "f", "c", "z"], RANKING, 5) == 0.5
    assert eb.recall_en_k([], RANKING, 5) == 0.0


def test_todos_esenciales():
    assert eb.todos_esenciales_en_k(["a", "e"], RANKING, 5)
    assert not eb.todos_esenciales_en_k(["a", "f"], RANKING, 5)


def test_mrr_primer_esencial():
    assert eb.rr_primer_esencial(["a"], RANKING) == 1.0
    assert eb.rr_primer_esencial(["z", "c"], RANKING) == 1 / 3
    assert eb.rr_primer_esencial(["z"], RANKING) == 0.0


def test_metricas_agregadas():
    filas = [
        {
            "ids_relevantes": ["a", "b"],
            "ids_esenciales": ["a"],
            "ranking5": RANKING[:5],
            "ranking20": RANKING,
        },
        {
            "ids_relevantes": ["f"],
            "ids_esenciales": ["f"],
            "ranking5": RANKING[:5],
            "ranking20": RANKING,
        },
    ]
    m = eb.metricas(filas)
    assert m["hit@5"] == 0.5
    assert m["recall@5"] == 0.5
    assert m["esenciales@5"] == 0.5
    assert m["mrr"] == (1 + 1 / 6) / 2


def test_curva_umbral_borde_inclusivo():
    curva = eb.curva_umbral([0.50, 0.60], [0.50, 0.45], [0.50, 0.51])
    assert curva[0] == {"umbral": 0.50, "rechazos_injustos": 0, "aceptaciones": 1}
    assert curva[1] == {"umbral": 0.51, "rechazos_injustos": 1, "aceptaciones": 0}


def test_recomendar_umbral():
    curva = eb.curva_umbral([0.50, 0.55, 0.60, 0.70], [0.40], [0.45, 0.50, 0.55, 0.60, 0.65])
    # rechazos: 0.45→0, 0.50→0, 0.55→1, 0.60→2, 0.65→3
    assert eb.recomendar_umbral(curva) == 0.50  # hay umbrales con 0: no se admite 1
    assert eb.recomendar_umbral(curva, max_rechazos=0) == 0.50
    # ninguno con 0 rechazos: se admite 1, el más alto con 1
    c1 = [
        {"umbral": 0.45, "rechazos_injustos": 1, "aceptaciones": 5},
        {"umbral": 0.46, "rechazos_injustos": 1, "aceptaciones": 4},
        {"umbral": 0.47, "rechazos_injustos": 2, "aceptaciones": 3},
    ]
    assert eb.recomendar_umbral(c1) == 0.46
    assert eb.recomendar_umbral([]) is None
    assert (
        eb.recomendar_umbral([{"umbral": 0.4, "rechazos_injustos": 5, "aceptaciones": 0}]) is None
    )


def test_cache_no_repite_llamadas(tmp_path):
    class Falso:
        llamadas = 0

        def embed_query(self, t):
            self.llamadas += 1
            return [float(len(t))]

    emb, ruta = Falso(), tmp_path / "c" / "e.json"
    assert eb.vectores_con_cache(["hola", "ab"], "m1", emb, ruta) == [[4.0], [2.0]]
    assert eb.vectores_con_cache(["hola", "ab"], "m1", emb, ruta) == [[4.0], [2.0]]
    assert emb.llamadas == 2
    eb.vectores_con_cache(["hola"], "m2", emb, ruta)  # otro modelo → otra clave
    assert emb.llamadas == 3
    assert eb.clave_cache("m1", "x") != eb.clave_cache("m2", "x")
