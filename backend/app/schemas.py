"""Modelos de la API: entrada (`PreguntaIn`) y salida (`RespuestaOut`) de POST /preguntar."""

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, Field, field_validator

AVISO_LEGAL = (
    "Esta información se basa únicamente en el texto del Reglamento (UE) 2024/1689 y "
    "no constituye asesoramiento legal. Consulta a un profesional cualificado."
)

MENSAJE_SIN_INFORMACION = (
    "No he encontrado esto en el Reglamento (UE) 2024/1689. Solo puedo responder preguntas "
    "sobre el texto de ese Reglamento y no he localizado información relevante sobre tu "
    "pregunta en él. Prueba a reformularla o consulta directamente el texto oficial."
)

LONGITUD_MAXIMA_PREGUNTA = 1000


def limpiar_pregunta(texto: str) -> str:
    """Sustituye saltos y tabuladores por espacios, elimina caracteres de control (Cc) y de
    formato (Cf: zero-width, marcas bidireccionales...) y colapsa los espacios."""
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = "".join(c for c in texto if unicodedata.category(c) not in ("Cc", "Cf"))
    return re.sub(r" {2,}", " ", texto).strip()


class PreguntaIn(BaseModel):
    pregunta: str = Field(min_length=1, max_length=LONGITUD_MAXIMA_PREGUNTA)

    @field_validator("pregunta", mode="before")
    @classmethod
    def _limpiar(cls, v: object) -> object:
        return limpiar_pregunta(v) if isinstance(v, str) else v


class AfirmacionOut(BaseModel):
    texto: str
    citas: list[int]


class CitaOut(BaseModel):
    n: int
    id: str
    cita: str
    tipo: str
    url: str


class MetaOut(BaseModel):
    modelo: str
    latencia_ms: int
    similitud_max: float


class RespuestaOut(BaseModel):
    estado: Literal["respondida", "sin_informacion"]
    afirmaciones: list[AfirmacionOut]
    citas: list[CitaOut]
    mensaje: str | None = None  # solo en sin_informacion: explica el límite del asistente
    aviso_legal: str = AVISO_LEGAL
    meta: MetaOut
