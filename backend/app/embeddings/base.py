"""Contrato de los embedders.

`Protocol` es el equivalente a una `interface` de TypeScript, pero estructural y sin
`implements`: cualquier clase con estos métodos cumple el contrato (tipado por patos).
"""

from typing import Protocol

DIMENSIONES = 1024  # bge-m3; debe coincidir con vector(1024) de la tabla fragmentos


class EmbeddingError(RuntimeError):
    """Fallo al obtener embeddings (nunca incluye credenciales en el mensaje)."""


class EmbeddingCuotaError(EmbeddingError):
    """Cloudflare siguió respondiendo 429 (límite o cuota) tras agotar los reintentos."""


class Embedder(Protocol):
    def embed_documents(self, textos: list[str]) -> list[list[float]]:
        """Embebe una lista de textos (uno por vector, en el mismo orden)."""
        ...

    def embed_query(self, texto: str) -> list[float]:
        """Embebe la pregunta de un usuario."""
        ...
