"""Descarga del dólar blue.

Historial diario: ArgentinaDatos (argentinadatos.com), con caché local. Cada
fila trae la cotización de compra y de venta de un día.

Cotización actual: DolarAPI (dolarapi.com), que además informa cuándo se
actualizó por última vez. Ambas son APIs comunitarias, no oficiales, y pueden
tardar en reflejar los movimientos del mercado.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

URL_BLUE = "https://api.argentinadatos.com/v1/cotizaciones/dolares/blue"

CACHE_DIR = Path.home() / ".cache" / "simulador-inversiones"
CACHE_TTL_SEGUNDOS = 3600  # el blue cambia durante el día
NOMBRE_CACHE = "dolar_blue.json"

# (fecha ISO, compra, venta)
Cotizacion = tuple[str, float, float]


def descargar_blue(usar_cache: bool = True) -> list[Cotizacion]:
    """Historial diario del dólar blue como (fecha ISO, compra, venta), ordenado por fecha.

    `compra` es el precio al que el mercado te compra un dólar (lo que recibís
    al vender); `venta`, el precio al que te lo vende (lo que pagás al comprar).
    Usa caché en disco durante 1 hora.
    """
    ruta = CACHE_DIR / NOMBRE_CACHE
    if usar_cache and ruta.exists() and time.time() - ruta.stat().st_mtime < CACHE_TTL_SEGUNDOS:
        return [tuple(fila) for fila in json.loads(ruta.read_text(encoding="utf-8"))]

    respuesta = httpx.get(URL_BLUE, timeout=30)
    respuesta.raise_for_status()
    filas = sorted(
        (fila["fecha"], float(fila["compra"]), float(fila["venta"]))
        for fila in respuesta.json()
        if fila.get("compra") is not None and fila.get("venta") is not None
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(filas), encoding="utf-8")
    return filas


def cierres_mensuales(
    cotizaciones: list[Cotizacion], campo: str
) -> list[tuple[str, float]]:
    """Última cotización de cada mes, como (AAAA-MM, valor).

    `campo` es 'compra' o 'venta'. Se queda con el dato de la última fecha
    disponible de cada mes.
    """
    if campo not in ("compra", "venta"):
        raise ValueError("El campo debe ser 'compra' o 'venta'")
    posicion = 1 if campo == "compra" else 2
    por_mes: dict[str, float] = {}
    for fila in sorted(cotizaciones):
        por_mes[fila[0][:7]] = fila[posicion]
    return sorted(por_mes.items())


URL_BLUE_ACTUAL = "https://dolarapi.com/v1/dolares/blue"

# Argentina no usa horario de verano, así que alcanza con un desfase fijo
# (zoneinfo necesitaría el paquete tzdata en Windows).
ZONA_ARGENTINA = timezone(timedelta(hours=-3))


@dataclass(frozen=True)
class CotizacionActual:
    compra: float
    venta: float
    actualizado: datetime  # cuándo actualizó la fuente el dato, en hora argentina


def _cotizacion_actual(datos: dict) -> CotizacionActual:
    actualizado = datetime.fromisoformat(datos["fechaActualizacion"].replace("Z", "+00:00"))
    return CotizacionActual(
        compra=float(datos["compra"]),
        venta=float(datos["venta"]),
        actualizado=actualizado.astimezone(ZONA_ARGENTINA),
    )


def descargar_blue_actual() -> CotizacionActual:
    """Cotización actual del blue con la hora en que la fuente la actualizó por última vez."""
    respuesta = httpx.get(URL_BLUE_ACTUAL, timeout=15)
    respuesta.raise_for_status()
    return _cotizacion_actual(respuesta.json())


URL_COTIZACIONES_ACTUALES = "https://dolarapi.com/v1/dolares"


def descargar_cotizaciones_actuales() -> dict[str, CotizacionActual]:
    """Cotización actual de cada tipo de dólar, indexada por 'casa' (oficial, blue, bolsa...).

    Cada tipo trae su propia hora de actualización: el oficial se actualiza solo
    en horario bancario, los financieros durante la rueda.
    """
    respuesta = httpx.get(URL_COTIZACIONES_ACTUALES, timeout=15)
    respuesta.raise_for_status()
    return {fila["casa"]: _cotizacion_actual(fila) for fila in respuesta.json()}
