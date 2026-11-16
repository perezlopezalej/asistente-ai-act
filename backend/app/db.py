"""Conexión a Postgres (Neon) con psycopg 3 y el tipo `vector` de pgvector registrado."""

from urllib.parse import unquote, urlsplit

import psycopg
from pgvector.psycopg import register_vector

from app.config import settings


class DatabaseError(RuntimeError):
    """Fallo de conexión; el mensaje nunca incluye la cadena de conexión."""


def censurar(mensaje: str, url: str) -> str:
    """Quita de `mensaje` la cadena de conexión y la contraseña (sustituidas por ***)."""
    secretos = [url, url.strip().strip("'\"")]
    try:
        password = urlsplit(url.strip().strip("'\"")).password
    except ValueError:
        password = None
    if password:
        secretos += [password, unquote(password)]
    # Los más largos primero, para que la URL completa no quede a medias por la contraseña.
    for secreto in sorted(set(filter(None, secretos)), key=len, reverse=True):
        mensaje = mensaje.replace(secreto, "***")
    return mensaje


def conectar(database_url: str | None = None) -> psycopg.Connection:
    url = database_url or settings.database_url
    if not url:
        raise DatabaseError("Falta DATABASE_URL (rellénala en el .env de la raíz del repo).")
    try:
        conn = psycopg.connect(url, autocommit=True)
    except psycopg.Error as e:
        # `from None`: no encadenamos la excepción original (podría llevar la cadena entera);
        # el mensaje de psycopg se incluye, pero censurado.
        raise DatabaseError(
            f"No se pudo conectar a la base de datos ({type(e).__name__}): {censurar(str(e), url)}"
        ) from None
    try:
        register_vector(conn)
    except psycopg.ProgrammingError:
        conn.close()
        raise DatabaseError(
            "El tipo 'vector' no existe: ejecuta db/migrations/001_fragmentos.sql en Neon."
        ) from None
    return conn
