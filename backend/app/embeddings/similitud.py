"""Similitud coseno en Python puro (para scripts de comprobación)."""

import math


def coseno(a: list[float], b: list[float]) -> float:
    """cos(a, b) = a·b / (|a|·|b|): 1 = misma dirección, 0 = ortogonales."""
    producto = sum(x * y for x, y in zip(a, b, strict=True))
    norma = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return producto / norma
