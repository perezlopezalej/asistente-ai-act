"""Ejecuta el parser y escribe data/processed/chunks.jsonl.

Uso (desde backend/): uv run python scripts/ingest.py
"""

import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.ingest.parser import parsear  # noqa: E402

HTML = RAIZ / "data" / "raw" / "CELEX_32024R1689_ES_TXT.html"
SALIDA = RAIZ / "data" / "processed" / "chunks.jsonl"


def main() -> None:
    if not HTML.exists():
        sys.exit(f"No existe {HTML}. Descárgalo a mano (ver README, sección Datos).")
    fragmentos = parsear(HTML)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    with SALIDA.open("w", encoding="utf-8", newline="\n") as f:
        for fr in fragmentos:
            f.write(fr.model_dump_json() + "\n")
    print(f"{len(fragmentos)} fragmentos -> {SALIDA}")
    print(dict(Counter(fr.tipo for fr in fragmentos)))


if __name__ == "__main__":
    main()
