"""Esquema de la salida del modelo y su validación (SIEMPRE en nuestro código)."""

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

# JSON Schema "pelado" (el que va en response_format.json_schema de Workers AI). Escrito a
# mano y no con model_json_schema(), que genera $defs/$ref que no todos los modelos admiten.
ESQUEMA_SALIDA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sin_informacion": {"type": "boolean"},
        "afirmaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string"},
                    "fragmentos": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["texto", "fragmentos"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["sin_informacion", "afirmaciones"],
    "additionalProperties": False,
}


class Afirmacion(BaseModel):
    model_config = ConfigDict(extra="ignore")

    texto: str = Field(min_length=1)
    fragmentos: list[str]


class SalidaModelo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sin_informacion: StrictBool
    afirmaciones: list[Afirmacion]


class SalidaInvalida(ValueError):
    """La salida del modelo no es JSON o no cumple el esquema."""


_VALLA = re.compile(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def parsear_salida(texto: str) -> SalidaModelo:
    """Texto del modelo -> `SalidaModelo`; tolera bloques ```json y texto alrededor del JSON."""
    limpio = texto.strip()
    valla = _VALLA.match(limpio)
    if valla:
        limpio = valla.group(1).strip()
    try:
        datos = json.loads(limpio)
    except json.JSONDecodeError:
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio == -1 or fin <= inicio:
            raise SalidaInvalida("la salida no contiene JSON") from None
        try:
            datos = json.loads(limpio[inicio : fin + 1])
        except json.JSONDecodeError:
            raise SalidaInvalida("la salida no es JSON válido") from None
    try:
        return SalidaModelo.model_validate(datos)
    except ValidationError:
        raise SalidaInvalida("la salida no cumple el esquema") from None
