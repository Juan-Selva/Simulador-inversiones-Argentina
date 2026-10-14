"""Descarga del valor diario de la UVA (Unidad de Valor Adquisitivo).

Fuente: ArgentinaDatos (argentinadatos.com), que replica la serie publicada por
el BCRA. La UVA se ajusta por CER, es decir, por inflación. API comunitaria, no
oficial: ante dudas, contrastar con las comunicaciones "B" del BCRA.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

URL_UVA = "https://api.argentinadatos.com/v1/finanzas/indices/uva"

CACHE_DIR = Path.home() / ".cache" / "simulador-inversiones"
CACHE_TTL_SEGUNDOS = 6 * 3600  # se publica una vez por día
NOMBRE_CACHE = "uva.json"

# (fecha ISO, valor)
ValorUva = tuple[str, float]


def descargar_uva(usar_cache: bool = True) -> list[ValorUva]:
    """Valor diario de la UVA como (fecha ISO, valor), ordenado por fecha."""
    ruta = CACHE_DIR / NOMBRE_CACHE
    if usar_cache and ruta.exists() and time.time() - ruta.stat().st_mtime < CACHE_TTL_SEGUNDOS:
        return [tuple(fila) for fila in json.loads(ruta.read_text(encoding="utf-8"))]

    respuesta = httpx.get(URL_UVA, timeout=30)
    respuesta.raise_for_status()
    filas = sorted(
        (fila["fecha"], float(fila["valor"]))
        for fila in respuesta.json()
        if fila.get("valor") is not None
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(filas), encoding="utf-8")
    return filas


def cierres_mensuales(valores: list[ValorUva]) -> list[tuple[str, float]]:
    """Último valor de cada mes, como (AAAA-MM, valor)."""
    por_mes: dict[str, float] = {}
    for fecha, valor in sorted(valores):
        por_mes[fecha[:7]] = valor
    return sorted(por_mes.items())
