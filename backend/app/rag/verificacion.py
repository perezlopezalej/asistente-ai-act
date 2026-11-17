"""Verificación determinista de las citas del modelo (lo más crítico del sistema).

Nada de lo que el modelo diga sobre "dónde" está una afirmación se acepta sin comprobarlo:
los ids deben ser de fragmentos que enviamos, cada afirmación necesita al menos un
artículo/anexo, y la cita legible, el tipo y la url salen siempre de la base de datos.
"""

import re
from dataclasses import dataclass, field

from app.rag.esquema import SalidaModelo
from app.rag.recuperacion import Fragmento
from app.schemas import AfirmacionOut, CitaOut

# Marcadores tipo "[1]" o "[1, 2]" que el modelo haya escrito: no coincidirían con nuestra
# numeración, así que se quitan del texto.
_MARCADORES = re.compile(r"\s*\[\d+(?:\s*[,;–-]\s*\d+)*\]")


@dataclass
class Verificacion:
    afirmaciones: list[AfirmacionOut] = field(default_factory=list)
    citas: list[CitaOut] = field(default_factory=list)
    afirmaciones_descartadas: int = 0
    ids_descartados: int = 0

    @property
    def vacia(self) -> bool:
        return not self.afirmaciones


def verificar_citas(salida: SalidaModelo, enviados: list[Fragmento]) -> Verificacion:
    por_id = {f.id: f for f in enviados}
    resultado = Verificacion()
    numeros: dict[str, int] = {}  # id -> n, por orden de primera aparición

    if salida.sin_informacion:
        return resultado  # se ignora cualquier afirmación que acompañe a la abstención

    for afirmacion in salida.afirmaciones:
        ids = list(dict.fromkeys(afirmacion.fragmentos))  # sin duplicados, en orden
        validos = [i for i in ids if i in por_id]
        resultado.ids_descartados += len(ids) - len(validos)
        texto = _MARCADORES.sub("", afirmacion.texto).strip()
        if not texto or not any(por_id[i].citable for i in validos):
            resultado.afirmaciones_descartadas += 1
            continue
        for i in validos:
            if i not in numeros:
                numeros[i] = len(numeros) + 1
                f = por_id[i]
                resultado.citas.append(
                    CitaOut(n=numeros[i], id=f.id, cita=f.cita, tipo=f.tipo, url=f.url_fuente)
                )
        resultado.afirmaciones.append(
            AfirmacionOut(texto=texto, citas=sorted(numeros[i] for i in validos))
        )
    return resultado
