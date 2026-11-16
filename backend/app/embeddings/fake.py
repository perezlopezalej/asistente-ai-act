"""Embedder falso y determinista para tests (sin red)."""

import hashlib

from app.embeddings.base import DIMENSIONES


class FakeEmbedder:
    def __init__(self, dimensiones: int = DIMENSIONES) -> None:
        self.model = "fake"
        self._dimensiones = dimensiones
        self.llamadas: list[list[str]] = []

    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        self.llamadas.append(list(textos))
        return [self._vector(t) for t in textos]

    def embed_query(self, texto: str) -> list[float]:
        return self._vector(texto)

    def _vector(self, texto: str) -> list[float]:
        """Mismo texto -> mismo vector; textos distintos -> vectores distintos."""
        digest = hashlib.sha256(texto.encode()).digest()
        return [(digest[i % len(digest)] - 127.5) / 127.5 for i in range(self._dimensiones)]
