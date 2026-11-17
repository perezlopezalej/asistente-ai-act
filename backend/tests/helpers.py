"""Utilidades compartidas por los tests del pipeline RAG (sin red ni base de datos)."""

from app.rag.recuperacion import Fragmento, Recuperacion


def frag(
    id_: str, tipo: str = "articulo", similitud: float = 0.8, texto: str = "Texto."
) -> Fragmento:
    return Fragmento(
        id=id_,
        tipo=tipo,
        cita=f"CITA DE {id_}",
        url_fuente=f"https://eur-lex.example/{id_}",
        texto=texto,
        similitud=similitud,
    )


def recuperacion_basica() -> Recuperacion:
    return Recuperacion(
        citables=[frag("art-5-ap-1", similitud=0.82), frag("art-6-ap-1", similitud=0.70)],
        considerandos=[frag("rct-27", "considerando", similitud=0.66)],
    )


def salida(*afirmaciones: tuple[str, list[str]], sin_informacion: bool = False) -> dict:
    return {
        "sin_informacion": sin_informacion,
        "afirmaciones": [{"texto": t, "fragmentos": f} for t, f in afirmaciones],
    }
