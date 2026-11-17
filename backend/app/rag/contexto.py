"""Montaje del contexto que se envía al modelo, con presupuesto de caracteres."""

import logging
from dataclasses import dataclass, field

from app.rag.prompt import neutralizar_etiquetas
from app.rag.recuperacion import Fragmento

log = logging.getLogger(__name__)

MARCA_TRUNCADO = "[…texto truncado…]"
SEPARADOR = "\n\n"


@dataclass
class Contexto:
    texto: str
    fragmentos: list[Fragmento] = field(default_factory=list)  # los que sí se enviaron
    omitidos: int = 0  # no cupieron en el presupuesto
    primero_truncado: bool = False


def formatear_fragmento(f: Fragmento, texto: str | None = None) -> str:
    lineas = [f'<fragmento id="{f.id}" tipo="{f.tipo}">', f"Fuente: {f.cita}"]
    if not f.citable:
        lineas.append("Uso: contexto interpretativo, no citable como fuente principal")
    cuerpo = f.texto if texto is None else texto
    lineas += [f"Texto: {neutralizar_etiquetas(cuerpo)}", "</fragmento>"]
    return "\n".join(lineas)


def construir_contexto(
    citables: list[Fragmento], considerandos: list[Fragmento], presupuesto: int
) -> Contexto:
    """Artículos/anexos primero y considerandos después, cada grupo por similitud descendente.

    Se añaden por orden hasta agotar `presupuesto` caracteres. Un fragmento que no cabe se
    salta (se prueba con los siguientes) y nunca se corta a la mitad, salvo el primero de
    todos si él solo supera el presupuesto: entonces se incluye truncado y se avisa.
    """
    ordenados = sorted(citables, key=lambda f: -f.similitud) + sorted(
        considerandos, key=lambda f: -f.similitud
    )
    bloques: list[str] = []
    incluidos: list[Fragmento] = []
    usado = 0
    omitidos = 0
    primero_truncado = False
    for i, f in enumerate(ordenados):
        bloque = formatear_fragmento(f)
        coste = len(bloque) + (len(SEPARADOR) if bloques else 0)
        if usado + coste > presupuesto and i == 0:
            hueco = presupuesto - len(formatear_fragmento(f, "")) - len(MARCA_TRUNCADO) - 1
            if hueco > 0:
                bloque = formatear_fragmento(f, f"{f.texto[:hueco]} {MARCA_TRUNCADO}")
                coste = len(bloque)
                primero_truncado = True
                log.warning(
                    "primer fragmento %s truncado: supera por sí solo el presupuesto de %d",
                    f.id,
                    presupuesto,
                )
        if usado + coste > presupuesto:
            omitidos += 1
            continue
        bloques.append(bloque)
        incluidos.append(f)
        usado += coste
    return Contexto(SEPARADOR.join(bloques), incluidos, omitidos, primero_truncado)
