"""Lectura de data/processed/chunks.jsonl."""

from pathlib import Path

from app.ingest.parser import Fragmento


def leer_chunks(ruta: Path) -> list[Fragmento]:
    with ruta.open(encoding="utf-8") as f:
        return [Fragmento.model_validate_json(linea) for linea in f if linea.strip()]
