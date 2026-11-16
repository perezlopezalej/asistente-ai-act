"""Diagnóstico de DATABASE_URL sin revelar la contraseña ni la cadena completa.

Uso (desde backend/): uv run python scripts/diagnostico_db.py
"""

import sys
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

import psycopg

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "backend"))

from app.config import settings  # noqa: E402
from app.db import censurar  # noqa: E402


def main() -> None:
    url = settings.database_url
    if not url:
        sys.exit("DATABASE_URL vacía o no definida (¿.env en la raíz del repo?).")

    print(f"Longitud total del valor: {len(url)}")
    print(f"Empieza por 'psql': {url.strip().lower().startswith('psql')}")
    print(f"Contiene comillas: {any(c in url for c in '\'"')}")
    print(f"Empieza/termina con comillas: {url[0] in '\'"' or url[-1] in '\'"'}")
    print(f"Contiene espacios o saltos de línea: {any(c.isspace() for c in url)}")

    limpia = url.strip().strip("'\"")
    try:
        partes = urlsplit(limpia)
        puerto = partes.port
    except ValueError as e:
        print(f"No se puede parsear la URL: {censurar(str(e), url)}")
        partes = None
        puerto = None

    if partes is not None:
        host = partes.hostname or ""
        password = unquote(partes.password) if partes.password else ""
        print(f"Esquema: {partes.scheme!r}")
        print(f"Usuario: {unquote(partes.username) if partes.username else None!r}")
        print(f"Host: {host!r}")
        print(f"Puerto: {puerto}")
        print(f"Base de datos: {partes.path.lstrip('/')!r}")
        print(f"Parámetros de la query: {dict(parse_qsl(partes.query))}")
        print(f"Longitud de la contraseña: {len(password)}")
        print(f"Host contiene '-pooler': {'-pooler' in host}")

    print(f"Versión de libpq: {psycopg.pq.version()}")

    try:
        with psycopg.connect(limpia, connect_timeout=15) as conn:
            version = conn.execute("select version()").fetchone()[0]
        print(f"Conexión: OK ({version})")
    except Exception as e:  # noqa: BLE001 - es un script de diagnóstico
        print(f"Conexión: FALLO ({type(e).__name__}): {censurar(str(e), url)}")


if __name__ == "__main__":
    main()
