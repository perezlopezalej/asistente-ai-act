"""Recuperación de fragmentos: dos búsquedas (citables y considerandos) en una conexión."""

from dataclasses import dataclass, field
from typing import Protocol

from pgvector import Vector

from app.db import conectar

TIPOS_CITABLES = ("articulo", "anexo")


@dataclass(frozen=True)
class Fragmento:
    id: str
    tipo: str
    cita: str
    url_fuente: str
    texto: str
    similitud: float
    numero: str = ""
    apartado: str | None = None
    titulo_articulo: str | None = None
    capitulo: str | None = None

    @property
    def citable(self) -> bool:
        return self.tipo in TIPOS_CITABLES


@dataclass
class Recuperacion:
    citables: list[Fragmento] = field(default_factory=list)  # artículos y anexos
    considerandos: list[Fragmento] = field(default_factory=list)

    @property
    def similitud_max(self) -> float:
        """Mejor similitud entre artículos/anexos (0.0 si no hay resultados)."""
        return max((f.similitud for f in self.citables), default=0.0)


class Buscador(Protocol):
    def buscar(
        self, vector: list[float], k_articulos: int, k_considerandos: int
    ) -> Recuperacion: ...


_SQL = """
    select id, tipo, numero, apartado, titulo_articulo, capitulo, texto, cita, url_fuente,
           similitud
    from buscar_fragmentos(%s::vector, %s, %s::text[])
"""


class BuscadorPostgres:
    """Usa la función SQL `buscar_fragmentos` de Neon (pgvector, similitud coseno)."""

    def buscar(self, vector: list[float], k_articulos: int, k_considerandos: int) -> Recuperacion:
        with conectar() as conn:
            citables = conn.execute(_SQL, (Vector(vector), k_articulos, list(TIPOS_CITABLES)))
            citables = [self._fila(f) for f in citables.fetchall()]
            considerandos = conn.execute(_SQL, (Vector(vector), k_considerandos, ["considerando"]))
            considerandos = [self._fila(f) for f in considerandos.fetchall()]
        return Recuperacion(citables, considerandos)

    @staticmethod
    def _fila(f: tuple) -> Fragmento:
        id_, tipo, numero, apartado, titulo, capitulo, texto, cita, url, similitud = f
        return Fragmento(
            id=id_,
            tipo=tipo,
            cita=cita,
            url_fuente=url,
            texto=texto,
            similitud=float(similitud),
            numero=numero,
            apartado=apartado,
            titulo_articulo=titulo,
            capitulo=capitulo,
        )
