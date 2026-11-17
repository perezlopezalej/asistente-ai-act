"""Buscador falso para tests (sin base de datos)."""

from app.rag.recuperacion import Recuperacion


class FakeBuscador:
    def __init__(self, recuperacion: Recuperacion) -> None:
        self._recuperacion = recuperacion
        self.llamadas: list[tuple[int, int]] = []

    def buscar(self, vector: list[float], k_articulos: int, k_considerandos: int) -> Recuperacion:
        self.llamadas.append((k_articulos, k_considerandos))
        return self._recuperacion
