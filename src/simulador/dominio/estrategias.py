"""Estrategias de inversión y ajuste por inflación.

Todas las tasas se expresan como fracciones (0.05 = 5 %), no como porcentajes.
Las funciones son puras: mismo input, mismo output, sin efectos secundarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

DIAS_ANIO = 365


@dataclass(frozen=True)
class Resultado:
    """Resultado de simular una inversión durante un período."""

    capital_inicial: float
    monto_final: float
    rendimiento_nominal: float
    inflacion_acumulada: float
    rendimiento_real: float
    monto_final_real: float  # en pesos del momento inicial


def plazo_fijo(capital: float, tna: float, dias: int) -> float:
    """Monto final de un plazo fijo tradicional (interés simple).

    interés = capital * TNA * días / 365
    """
    if capital < 0:
        raise ValueError("El capital no puede ser negativo")
    if dias < 0:
        raise ValueError("Los días no pueden ser negativos")
    return capital * (1 + tna * dias / DIAS_ANIO)


def plazo_fijo_renovado(capital: float, tna: float, dias_totales: int, plazo: int = 30) -> float:
    """Plazo fijo renovado cada `plazo` días, capitalizando el interés.

    Si `dias_totales` no es múltiplo de `plazo`, el último tramo es más corto.
    """
    if plazo <= 0:
        raise ValueError("El plazo debe ser positivo")
    monto = capital
    restantes = dias_totales
    while restantes > 0:
        tramo = min(plazo, restantes)
        monto = plazo_fijo(monto, tna, tramo)
        restantes -= tramo
    return monto


def inflacion_acumulada(variaciones_mensuales: Iterable[float]) -> float:
    """Inflación acumulada a partir de variaciones mensuales (0.04 = 4 %)."""
    factor = 1.0
    for v in variaciones_mensuales:
        factor *= 1 + v
    return factor - 1


def rendimiento_real(rendimiento_nominal: float, inflacion: float) -> float:
    """Rendimiento ajustado por inflación (ecuación de Fisher)."""
    return (1 + rendimiento_nominal) / (1 + inflacion) - 1


def _armar_resultado(capital: float, monto_final: float, inflacion: float) -> Resultado:
    nominal = monto_final / capital - 1 if capital else 0.0
    real = rendimiento_real(nominal, inflacion)
    return Resultado(
        capital_inicial=capital,
        monto_final=monto_final,
        rendimiento_nominal=nominal,
        inflacion_acumulada=inflacion,
        rendimiento_real=real,
        monto_final_real=capital * (1 + real),
    )


def simular_plazo_fijo(
    capital: float,
    tna: float,
    variaciones_mensuales: list[float],
    renovar: bool = True,
) -> Resultado:
    """Simula un plazo fijo durante tantos meses como variaciones de inflación se pasen.

    Cada mes se aproxima a 30 días, y la comparación se hace contra la inflación
    acumulada de esos mismos meses.
    """
    meses = len(variaciones_mensuales)
    dias = meses * 30
    if renovar:
        monto = plazo_fijo_renovado(capital, tna, dias, plazo=30)
    else:
        monto = plazo_fijo(capital, tna, dias)

    return _armar_resultado(capital, monto, inflacion_acumulada(variaciones_mensuales))


def simular_dolar(
    capital: float,
    precio_compra: float,
    precio_venta: float,
    inflacion: float,
) -> Resultado:
    """Comprar dólares al inicio del período y venderlos al final.

    `precio_compra` es lo que se paga en pesos por cada dólar al empezar y
    `precio_venta` lo que se recibe por cada dólar al terminar. Si el mercado
    cotiza dos precios (como el blue), se pasa el precio al que el mercado
    vende como `precio_compra` y el precio al que el mercado compra como
    `precio_venta`, así el spread queda incluido. No incluye comisiones ni
    impuestos. `inflacion` es la inflación acumulada del período.
    """
    if capital < 0:
        raise ValueError("El capital no puede ser negativo")
    if precio_compra <= 0 or precio_venta <= 0:
        raise ValueError("Los precios del dólar deben ser positivos")

    dolares = capital / precio_compra
    return _armar_resultado(capital, dolares * precio_venta, inflacion)
