"""Contrato de los modelos de lenguaje (mismo patrón que `Embedder`)."""

from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Fallo al generar (el mensaje nunca incluye credenciales ni el contenido del prompt)."""


class LLMCuotaError(LLMError):
    """El proveedor rechazó la petición por límite de peticiones o cuota agotada."""


class LLMTruncadoError(LLMError):
    """La generación se cortó por `max_tokens` (finish_reason == "length"); no se reintenta."""


@dataclass
class RespuestaLLM:
    texto: str
    tokens_entrada: int | None = None
    tokens_salida: int | None = None


class LLM(Protocol):
    model: str

    def generar(self, system: str, usuario: str, esquema: dict[str, Any]) -> RespuestaLLM:
        """Una petición al modelo; `esquema` es el JSON Schema "pelado" de la salida."""
        ...
