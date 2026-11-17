"""LLM falso para tests (sin red): devuelve respuestas guionizadas."""

import json
from typing import Any

from app.llm.base import RespuestaLLM


class FakeLLM:
    """Cada llamada consume la siguiente respuesta del guion.

    Una respuesta puede ser un `str` (texto crudo), un `dict` (se serializa a JSON) o una
    excepción (se lanza). Cuando el guion se acaba se repite la última.
    """

    def __init__(self, respuestas: list[str | dict | Exception], model: str = "fake-llm") -> None:
        self.model = model
        self._respuestas = list(respuestas)
        self.llamadas: list[dict[str, Any]] = []

    def generar(self, system: str, usuario: str, esquema: dict[str, Any]) -> RespuestaLLM:
        self.llamadas.append({"system": system, "usuario": usuario, "esquema": esquema})
        indice = min(len(self.llamadas), len(self._respuestas)) - 1
        respuesta = self._respuestas[indice]
        if isinstance(respuesta, Exception):
            raise respuesta
        texto = respuesta if isinstance(respuesta, str) else json.dumps(respuesta)
        return RespuestaLLM(texto, tokens_entrada=100, tokens_salida=50)
