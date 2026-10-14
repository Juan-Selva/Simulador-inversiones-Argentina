"""Lectura de números escritos por una persona en formato argentino."""

from __future__ import annotations

import math
import re

# 1.000 / 12.345 / 1.234.567: puntos como separador de miles (el primer grupo no empieza en 0).
_CON_MILES = re.compile(r"^[1-9]\d{0,2}(\.\d{3})+$")


def parsear_numero(texto: str) -> float:
    """Convierte '1.000.000', '35,5', '$ 2.500' o '3.5' en un número.

    Si hay coma, es el separador decimal y los puntos son de miles. Sin coma,
    un número como '1.000' o '12.345' se toma como miles; el resto ('35.5',
    '0.125') como decimal.
    """
    limpio = texto.strip().replace("$", "").replace("%", "").replace(" ", "")
    if not limpio:
        raise ValueError("Completá todos los campos")
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif _CON_MILES.match(limpio):
        limpio = limpio.replace(".", "")
    try:
        valor = float(limpio)
    except ValueError:
        raise ValueError(f"'{texto.strip()}' no es un número válido") from None
    if not math.isfinite(valor):
        raise ValueError(f"'{texto.strip()}' no es un número válido")
    return valor


def parsear_entero(texto: str) -> int:
    """Como parsear_numero, pero exige un número entero."""
    valor = parsear_numero(texto)
    if valor != int(valor):
        raise ValueError(f"'{texto.strip()}' tiene que ser un número entero")
    return int(valor)
