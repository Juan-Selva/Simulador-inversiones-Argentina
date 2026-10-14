"""Descarga de series de tiempo desde la API de datos.gob.ar con caché local.

Documentación de la API: https://datosgobar.github.io/series-tiempo-ar-api/
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path

import httpx

API_URL = "https://apis.datos.gob.ar/series/api/series/"

# IPC nivel general nacional (INDEC), base diciembre 2016, frecuencia mensual.
# ID verificado contra la API. El INDEC publica con ~1 mes de retraso.
IPC_NIVEL_GENERAL = "148.3_INIVELNAL_DICI_M_26"

CACHE_DIR = Path.home() / ".cache" / "simulador-inversiones"
CACHE_TTL_SEGUNDOS = 24 * 3600


def _ruta_cache(serie_id: str) -> Path:
    return CACHE_DIR / f"{serie_id}.json"


def descargar_serie(serie_id: str, usar_cache: bool = True) -> list[tuple[str, float]]:
    """Devuelve la serie como lista de (fecha ISO, valor), ordenada por fecha.

    Usa caché en disco durante 24 horas para no depender de que la API esté arriba.
    """
    ruta = _ruta_cache(serie_id)
    if usar_cache and ruta.exists() and time.time() - ruta.stat().st_mtime < CACHE_TTL_SEGUNDOS:
        return [tuple(fila) for fila in json.loads(ruta.read_text(encoding="utf-8"))]

    respuesta = httpx.get(
        API_URL,
        params={"ids": serie_id, "format": "json", "limit": 1000},
        timeout=15,
    )
    respuesta.raise_for_status()
    filas = sorted(
        (fecha, valor) for fecha, valor in respuesta.json()["data"] if valor is not None
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(filas), encoding="utf-8")
    return filas


def variaciones_mensuales(niveles: list[tuple[str, float]]) -> list[float]:
    """Convierte una serie de niveles de índice en variaciones mensuales."""
    return [
        actual[1] / previo[1] - 1
        for previo, actual in zip(niveles, niveles[1:])
    ]


def ultimas_variaciones(
    niveles: list[tuple[str, float]], meses: int
) -> list[tuple[str, float]]:
    """Variación mensual de los últimos `meses` meses, como (fecha, variación).

    La fecha es la del mes al que corresponde la variación. Para obtener N
    variaciones hacen falta N + 1 niveles del índice.
    """
    if meses < 1:
        raise ValueError("Los meses deben ser al menos 1")
    if len(niveles) < meses + 1:
        raise ValueError(
            f"La serie tiene {len(niveles)} datos y se necesitan {meses + 1} para {meses} meses"
        )
    tramo = niveles[-(meses + 1):]
    return [
        (actual[0], actual[1] / previo[1] - 1)
        for previo, actual in zip(tramo, tramo[1:])
    ]


def mes_anterior(fecha_iso: str) -> str:
    """Mes anterior a una fecha ISO, como 'AAAA-MM' (2026-01-01 -> 2025-12)."""
    anio, mes = int(fecha_iso[:4]), int(fecha_iso[5:7])
    if mes == 1:
        return f"{anio - 1}-12"
    return f"{anio}-{mes - 1:02d}"


def valor_del_mes(serie: list[tuple[str, float]], mes: str) -> float:
    """Valor de una serie para un mes dado como 'AAAA-MM'."""
    for fecha, valor in serie:
        if fecha[:7] == mes:
            return valor
    raise ValueError(f"La serie no tiene datos para {mes}")


def mes_pasado(hoy: date) -> str:
    """Mes calendario anterior a `hoy`, como 'AAAA-MM'."""
    return mes_anterior(hoy.isoformat())


def ultimo_mes(serie: list[tuple[str, float]]) -> str:
    """Último mes con datos de la serie, como 'AAAA-MM'."""
    if not serie:
        raise ValueError("La serie está vacía")
    return serie[-1][0][:7]


def variacion_del_mes(niveles: list[tuple[str, float]], mes: str) -> float:
    """Inflación de un mes ('AAAA-MM') respecto del mes anterior."""
    return valor_del_mes(niveles, mes) / valor_del_mes(niveles, mes_anterior(mes)) - 1


def variacion_interanual(niveles: list[tuple[str, float]], mes: str) -> float:
    """Inflación de un mes ('AAAA-MM') respecto del mismo mes del año anterior."""
    mismo_mes_anio_anterior = f"{int(mes[:4]) - 1:04d}-{mes[5:7]}"
    return valor_del_mes(niveles, mes) / valor_del_mes(niveles, mismo_mes_anio_anterior) - 1
