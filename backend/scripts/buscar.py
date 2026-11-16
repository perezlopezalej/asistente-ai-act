"""Búsqueda manual: embebe la pregunta y muestra el top 5 de fragmentos.

Uso (desde backend/):
    uv run python scripts/buscar.py "¿Qué prácticas de IA están prohibidas?"
    uv run python scripts/buscar.py "..." --tipo articulo   # debe seguir devolviendo 5
"""

import argparse
import sys
from pathlib import Path

from pgvector import Vector

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.db import conectar  # noqa: E402
from app.embeddings.factory import crear_embedder  # noqa: E402

TOP = 5


def main() -> None:
    parser = argparse.ArgumentParser(description="Busca fragmentos del AI Act.")
    parser.add_argument("pregunta")
    parser.add_argument("--tipo", choices=["articulo", "considerando", "anexo"])
    args = parser.parse_args()
    # Evita que un carácter no representable en la consola de Windows corte la salida.
    sys.stdout.reconfigure(errors="replace")

    vector = crear_embedder().embed_query(args.pregunta)
    tipos = [args.tipo] if args.tipo else None

    with conectar() as conn:
        filas = conn.execute(
            "select cita, similitud, texto from buscar_fragmentos(%s::vector, %s, %s::text[])",
            (Vector(vector), TOP, tipos),
        ).fetchall()

    filtro = f" (tipo={args.tipo})" if args.tipo else ""
    print(f"{len(filas)} resultados{filtro} para: {args.pregunta}\n")
    for cita, similitud, texto in filas:
        # Un solo print por resultado (cita + texto) y con flush, para que no se separen.
        print(f"{similitud:.3f}  {cita}\n       {texto[:120]}…\n", flush=True)


if __name__ == "__main__":
    main()
