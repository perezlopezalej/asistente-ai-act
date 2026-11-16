import psycopg
import pytest

from app import db
from app.db import DatabaseError, censurar, conectar

URL = "postgresql://usuario:s3cr3t%40pass@ep-algo-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require"


def test_censura_la_contrasena():
    msg = 'connection failed: password authentication failed for user "usuario" (s3cr3t@pass)'
    out = censurar(msg, URL)
    assert "s3cr3t" not in out
    assert "***" in out
    assert "usuario" in out  # el resto del mensaje se conserva


def test_censura_la_contrasena_codificada_en_la_url():
    assert "s3cr3t%40pass" not in censurar("fallo con s3cr3t%40pass", URL)


def test_censura_la_cadena_completa():
    out = censurar(f"error en {URL} al conectar", URL)
    assert out == "error en *** al conectar"


def test_censura_url_con_comillas():
    out = censurar("x s3cr3t@pass y", f'"{URL}"')
    assert "s3cr3t" not in out


def test_censura_sin_contrasena_no_rompe():
    assert censurar("hola", "postgresql://u@host/db") == "hola"


def test_conectar_no_filtra_secretos_en_el_error(monkeypatch):
    def falla(url, **kw):
        raise psycopg.OperationalError(f"fallo conectando con {url} (clave s3cr3t@pass)")

    monkeypatch.setattr(db.psycopg, "connect", falla)
    with pytest.raises(DatabaseError) as exc:
        conectar(URL)
    texto = str(exc.value)
    assert "OperationalError" in texto
    assert "s3cr3t" not in texto
    assert "neon.tech" not in texto  # la cadena completa se sustituye entera
