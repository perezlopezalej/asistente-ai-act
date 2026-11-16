"""Texto que se embebe (cabecera de contexto + texto) y hash de contenido."""

import hashlib

from app.ingest.parser import Fragmento


def cabecera(fr: Fragmento) -> str:
    """Contexto del fragmento: "Artículo 5. Prácticas de IA prohibidas. Apartado 1".

    Se deriva de `cita`, que ya recoge el apartado/punto/sección (p. ej. art. 3:
    "Artículo 3, punto 1 («sistema de IA»)"), y del título si lo hay.
    """
    base, _, sufijo = fr.cita.partition(", ")
    partes = [base]
    if fr.titulo_articulo:
        partes.append(fr.titulo_articulo)
    if sufijo:
        partes.append(sufijo[0].upper() + sufijo[1:])
    return ". ".join(partes)


def texto_para_embedding(fr: Fragmento) -> str:
    """Cabecera + texto. En la base de datos se guarda el texto original por separado."""
    return f"{cabecera(fr)}: {fr.texto}"


def calcular_hash(texto_embebido: str, modelo: str) -> str:
    """Hash estable de lo que determina el vector: texto embebido + modelo."""
    return hashlib.sha256(f"{modelo}\n{texto_embebido}".encode()).hexdigest()
