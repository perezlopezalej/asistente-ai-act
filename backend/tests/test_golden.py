"""Tests (sin red ni BD) del validador del conjunto de prueba `evals/golden.jsonl`."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "validar_golden", RAIZ / "evals" / "validar_golden.py"
)
vg = importlib.util.module_from_spec(_spec)
sys.modules["validar_golden"] = vg
_spec.loader.exec_module(vg)


def _escribir(ruta: Path, filas: list[dict]) -> Path:
    ruta.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in filas) + "\n", "utf-8")
    return ruta


@pytest.fixture
def chunks(tmp_path):
    filas = [
        {"id": "art-1", "tipo": "articulo", "cita": "Artículo 1", "texto": "uno"},
        {"id": "art-2", "tipo": "articulo", "cita": "Artículo 2", "texto": "dos"},
        {"id": "rct-1", "tipo": "considerando", "cita": "Considerando 1", "texto": "c"},
    ]
    return _escribir(tmp_path / "chunks.jsonl", filas)


def _fila(**cambios) -> dict:
    base = {
        "id": "g-001",
        "pregunta": "¿Qué dice el artículo uno?",
        "tipo": "directa",
        "ids_relevantes": ["art-1"],
        "ids_esenciales": ["art-1"],
        "debe_abstenerse": False,
        "confianza_etiqueta": "alta",
        "notas": "Porque sí.",
    }
    base.update(cambios)
    return base


def _validar(tmp_path, chunks, filas):
    golden = _escribir(tmp_path / "golden.jsonl", filas)
    return vg.validar(golden, chunks, ruta_coloquiales=None, comprobar_conteos=False)


# --- golden real ---


def test_golden_real_es_valido():
    assert vg.validar() == []


def test_golden_real_cubre_todos_los_tipos():
    filas = vg.cargar_jsonl(vg.GOLDEN)
    assert len(filas) == 40
    for tipo, esperado in vg.CONTEOS_ESPERADOS.items():
        assert sum(1 for f in filas if f["tipo"] == tipo) == esperado


def test_revision_cubre_cada_pregunta():
    md = vg.generar_revision()
    for fila in vg.cargar_jsonl(vg.GOLDEN):
        assert f"| {fila['id']}" in md
    assert vg.REVISION.read_text(encoding="utf-8") == md, "REVISION.md desactualizado: regenerar"


# --- casos sintéticos ---


def test_fila_valida(tmp_path, chunks):
    assert _validar(tmp_path, chunks, [_fila()]) == []


def test_id_inexistente(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(ids_relevantes=["art-99"], ids_esenciales=[])])
    assert any("inexistente" in e and "art-99" in e for e in errores)


def test_considerando_no_permitido(tmp_path, chunks):
    errores = _validar(
        tmp_path, chunks, [_fila(ids_relevantes=["rct-1"], ids_esenciales=["rct-1"])]
    )
    assert any("considerandos" in e for e in errores)


def test_ids_repetidos_en_una_pregunta(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(ids_relevantes=["art-1", "art-1"])])
    assert any("repetidos" in e for e in errores)


def test_esencial_fuera_de_relevantes(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(ids_esenciales=["art-2"])])
    assert any("ids_esenciales no incluidos" in e for e in errores)


def test_abstencion_con_ids(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(tipo="sin_respuesta", debe_abstenerse=True)])
    assert any("debe_abstenerse=true pero hay ids" in e for e in errores)


def test_sin_abstencion_sin_ids(tmp_path, chunks):
    errores = _validar(
        tmp_path, chunks, [_fila(ids_relevantes=[], ids_esenciales=[], debe_abstenerse=False)]
    )
    assert any("no hay ids_esenciales" in e for e in errores)


def test_abstencion_incoherente_con_el_tipo(tmp_path, chunks):
    fila = _fila(tipo="sin_respuesta", ids_relevantes=[], ids_esenciales=[], debe_abstenerse=False)
    errores = _validar(tmp_path, chunks, [fila])
    assert any("no es coherente con el tipo" in e for e in errores)


def test_tipo_invalido(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(tipo="inventado")])
    assert any("tipo inválido" in e for e in errores)


def test_confianza_invalida(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(confianza_etiqueta="baja")])
    assert any("confianza_etiqueta" in e for e in errores)


def test_abstenerse_no_bool(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(debe_abstenerse="no")])
    assert any("debe ser bool" in e for e in errores)


def test_id_de_pregunta_duplicado(tmp_path, chunks):
    errores = _validar(tmp_path, chunks, [_fila(), _fila(pregunta="Otra pregunta distinta")])
    assert any("id duplicado" in e for e in errores)


def test_pregunta_duplicada_normalizada(tmp_path, chunks):
    filas = [_fila(), _fila(id="g-002", pregunta="  ¿QUÉ dice  el artículo UNO? ")]
    errores = _validar(tmp_path, chunks, filas)
    assert any("pregunta duplicada" in e for e in errores)


def test_faltan_campos(tmp_path, chunks):
    fila = _fila()
    del fila["notas"]
    errores = _validar(tmp_path, chunks, [fila])
    assert any("faltan campos" in e for e in errores)


def test_coloquiales_deben_coincidir_con_el_txt(tmp_path, chunks):
    golden = _escribir(tmp_path / "golden.jsonl", [_fila(tipo="coloquial")])
    txt = tmp_path / "mis_preguntas.txt"
    txt.write_text("Una pregunta distinta\n", encoding="utf-8")
    errores = vg.validar(golden, chunks, ruta_coloquiales=txt, comprobar_conteos=False)
    assert any("coloquiales no coinciden" in e for e in errores)

    txt.write_text("¿Qué dice el artículo uno?\n\n", encoding="utf-8")
    assert vg.validar(golden, chunks, ruta_coloquiales=txt, comprobar_conteos=False) == []


def test_conteos_por_tipo(tmp_path, chunks):
    golden = _escribir(tmp_path / "golden.jsonl", [_fila()])
    errores = vg.validar(golden, chunks, ruta_coloquiales=None)
    assert any("se esperaban 15" in e for e in errores)
