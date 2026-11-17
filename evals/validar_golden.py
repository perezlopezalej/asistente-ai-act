"""Valida `evals/golden.jsonl` frente a `data/processed/chunks.jsonl` y genera `REVISION.md`.

Sin red, sin base de datos y sin dependencias externas.

Uso (desde la raíz del repositorio):
    python evals/validar_golden.py              # valida; código de salida 1 si hay errores
    python evals/validar_golden.py --revision   # regenera evals/REVISION.md (valida antes)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GOLDEN = RAIZ / "evals" / "golden.jsonl"
CHUNKS = RAIZ / "data" / "processed" / "chunks.jsonl"
COLOQUIALES = RAIZ / "evals" / "mis_preguntas.txt"
REVISION = RAIZ / "evals" / "REVISION.md"

TIPOS = ("directa", "coloquial", "sin_respuesta", "caso_concreto", "adversaria")
TIPOS_SIN_RESPUESTA = ("sin_respuesta", "adversaria")
CONFIANZAS = ("alta", "media")
CONTEOS_ESPERADOS = {
    "directa": 15,
    "coloquial": 10,
    "sin_respuesta": 8,
    "caso_concreto": 4,
    "adversaria": 3,
}
CAMPOS = (
    "id",
    "pregunta",
    "tipo",
    "ids_relevantes",
    "ids_esenciales",
    "debe_abstenerse",
    "confianza_etiqueta",
    "notas",
)
CAMPOS_OPCIONALES = ("afectada_omnibus",)
PATRON_ID = re.compile(r"^g-\d{3}$")


def _normalizar(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip().casefold()


def cargar_jsonl(ruta: Path) -> list[dict]:
    with ruta.open(encoding="utf-8") as fh:
        return [json.loads(linea) for linea in fh if linea.strip()]


def _validar_fila(fila: dict, chunks: dict[str, dict], etiqueta: str) -> list[str]:
    errores: list[str] = []
    faltan = [c for c in CAMPOS if c not in fila]
    if faltan:
        return [f"{etiqueta}: faltan campos {faltan}"]
    sobran = [c for c in fila if c not in CAMPOS + CAMPOS_OPCIONALES]
    if sobran:
        errores.append(f"{etiqueta}: campos desconocidos {sobran}")

    if not isinstance(fila["id"], str) or not PATRON_ID.match(fila["id"]):
        errores.append(f"{etiqueta}: id con formato inválido {fila['id']!r} (esperado g-NNN)")
    if not isinstance(fila["pregunta"], str) or not fila["pregunta"].strip():
        errores.append(f"{etiqueta}: pregunta vacía")
    if not isinstance(fila["notas"], str) or not fila["notas"].strip():
        errores.append(f"{etiqueta}: notas vacías")
    if fila["tipo"] not in TIPOS:
        errores.append(f"{etiqueta}: tipo inválido {fila['tipo']!r}")
    if fila["confianza_etiqueta"] not in CONFIANZAS:
        errores.append(f"{etiqueta}: confianza_etiqueta inválida {fila['confianza_etiqueta']!r}")
    if not isinstance(fila["debe_abstenerse"], bool):
        errores.append(f"{etiqueta}: debe_abstenerse debe ser bool")
    if "afectada_omnibus" in fila:
        if fila["afectada_omnibus"] is not True:
            errores.append(f"{etiqueta}: afectada_omnibus, si existe, debe ser true")
        if fila["confianza_etiqueta"] != "media":
            errores.append(f"{etiqueta}: afectada_omnibus exige confianza_etiqueta=media")

    listas_ok = True
    for campo in ("ids_relevantes", "ids_esenciales"):
        valor = fila[campo]
        if not isinstance(valor, list) or not all(isinstance(i, str) for i in valor):
            errores.append(f"{etiqueta}: {campo} debe ser una lista de str")
            listas_ok = False
            continue
        repetidos = sorted({i for i in valor if valor.count(i) > 1})
        if repetidos:
            errores.append(f"{etiqueta}: ids repetidos en {campo}: {repetidos}")
        for i in valor:
            if i not in chunks:
                errores.append(f"{etiqueta}: {campo} contiene un id inexistente: {i}")
            elif chunks[i]["tipo"] == "considerando":
                errores.append(f"{etiqueta}: {campo} no admite considerandos: {i}")
    if not listas_ok:
        return errores

    relevantes, esenciales = fila["ids_relevantes"], fila["ids_esenciales"]
    fuera = [i for i in esenciales if i not in relevantes]
    if fuera:
        errores.append(f"{etiqueta}: ids_esenciales no incluidos en ids_relevantes: {fuera}")

    if isinstance(fila["debe_abstenerse"], bool):
        if fila["debe_abstenerse"] and (relevantes or esenciales):
            errores.append(f"{etiqueta}: debe_abstenerse=true pero hay ids")
        if not fila["debe_abstenerse"] and not esenciales:
            errores.append(f"{etiqueta}: debe_abstenerse=false pero no hay ids_esenciales")
        if fila["tipo"] in TIPOS and fila["debe_abstenerse"] != (
            fila["tipo"] in TIPOS_SIN_RESPUESTA
        ):
            errores.append(
                f"{etiqueta}: debe_abstenerse={fila['debe_abstenerse']} no es coherente "
                f"con el tipo {fila['tipo']}"
            )
    return errores


def validar(
    ruta_golden: Path = GOLDEN,
    ruta_chunks: Path = CHUNKS,
    ruta_coloquiales: Path | None = COLOQUIALES,
    comprobar_conteos: bool = True,
) -> list[str]:
    """Devuelve la lista de errores (vacía si el golden es válido)."""
    chunks = {c["id"]: c for c in cargar_jsonl(ruta_chunks)}
    try:
        filas = cargar_jsonl(ruta_golden)
    except json.JSONDecodeError as exc:
        return [f"golden: JSON inválido ({exc})"]

    errores: list[str] = []
    vistos_id: dict[str, int] = {}
    vistas_pregunta: dict[str, str] = {}
    for n, fila in enumerate(filas, 1):
        etiqueta = f"línea {n} ({fila.get('id', '?')})"
        errores += _validar_fila(fila, chunks, etiqueta)
        if fila.get("id") in vistos_id:
            errores.append(f"{etiqueta}: id duplicado (ya en la línea {vistos_id[fila['id']]})")
        vistos_id.setdefault(fila.get("id"), n)
        clave = _normalizar(str(fila.get("pregunta", "")))
        if clave in vistas_pregunta:
            errores.append(f"{etiqueta}: pregunta duplicada de {vistas_pregunta[clave]}")
        vistas_pregunta.setdefault(clave, str(fila.get("id")))

    if comprobar_conteos:
        por_tipo = {t: sum(1 for f in filas if f.get("tipo") == t) for t in TIPOS}
        for tipo, esperado in CONTEOS_ESPERADOS.items():
            if por_tipo[tipo] != esperado:
                errores.append(f"golden: se esperaban {esperado} «{tipo}» y hay {por_tipo[tipo]}")

    if ruta_coloquiales is not None:
        propias = [
            ln.strip()
            for ln in ruta_coloquiales.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
        en_golden = [f["pregunta"] for f in filas if f.get("tipo") == "coloquial"]
        if sorted(en_golden) != sorted(propias):
            errores.append(
                "golden: las preguntas coloquiales no coinciden exactamente con "
                f"{ruta_coloquiales.name} ({len(en_golden)} en el golden, {len(propias)} en el txt)"
            )
    return errores


# --- REVISION.md ---


def _celda(texto: str) -> str:
    return " ".join(texto.split()).replace("|", "/")


def _cita_legible(chunk: dict, esencial: bool) -> str:
    texto = _celda(chunk["texto"])
    fragmento = texto if len(texto) <= 150 else texto[:150].rstrip() + "…"
    marca = "★ " if esencial else ""
    return f"{marca}**{_celda(chunk['cita'])}** (`{chunk['id']}`): {fragmento}"


def generar_revision(ruta_golden: Path = GOLDEN, ruta_chunks: Path = CHUNKS) -> str:
    chunks = {c["id"]: c for c in cargar_jsonl(ruta_chunks)}
    filas = cargar_jsonl(ruta_golden)
    dudosas = sum(1 for f in filas if f["confianza_etiqueta"] == "media")
    lineas = [
        "# Revisión manual del conjunto de prueba",
        "",
        "Generado por `python evals/validar_golden.py --revision`; no editar a mano "
        "(se edita `golden.jsonl` y se regenera).",
        "",
        f"{len(filas)} preguntas; ⚠ = confianza de la etiqueta «media» ({dudosas}); "
        "★ = id esencial (imprescindible para responder bien); 🅾 = afectada por el AI Omnibus "
        "(Reglamento (UE) 2026/1744), que el corpus no incluye.",
        "",
        "| id | tipo | pregunta | ids y cita legible | justificación |",
        "|---|---|---|---|---|",
    ]
    for fila in filas:
        if fila["debe_abstenerse"]:
            ids = "— (debe abstenerse)"
        else:
            esenciales = set(fila["ids_esenciales"])
            ids = "<br>".join(
                _cita_legible(chunks[i], i in esenciales) for i in fila["ids_relevantes"]
            )
        marca = " ⚠" if fila["confianza_etiqueta"] == "media" else ""
        marca += " 🅾" if fila.get("afectada_omnibus") else ""
        lineas.append(
            f"| {fila['id']}{marca} | {fila['tipo']} | {_celda(fila['pregunta'])} | {ids} | "
            f"{_celda(fila['notas'])} |"
        )
    return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--revision", action="store_true", help="regenera evals/REVISION.md")
    args = parser.parse_args(argv)

    errores = validar()
    if errores:
        print("golden.jsonl NO es válido:", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("golden.jsonl válido")
    if args.revision:
        REVISION.write_text(generar_revision(), encoding="utf-8", newline="\n")
        print(f"escrito {REVISION.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
