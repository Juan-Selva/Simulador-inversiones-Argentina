"""Pagar de contado o en cuotas sin interés.

Pagar en cuotas sin interés te deja la plata en el bolsillo un tiempo más, y
ese tiempo vale algo si tu plata rinde. La comparación se hace en pesos de
hoy: se calcula cuánto valen hoy las cuotas descontadas a lo que rinde tu
plata (valor presente) y se lo compara con el precio de contado. Si las
cuotas valen menos que el contado, convienen las cuotas.

Supuestos: la primera cuota se paga a los 30 días y las demás una por mes,
todas de igual monto. Son funciones puras: sin red ni archivos.
"""

from __future__ import annotations

from simulador.dominio.estrategias import plazo_fijo

MESES_HASTA_LA_PRIMERA_CUOTA = 1


def _validar(precio_lista: float, cuotas: int, descuento: float) -> None:
    if precio_lista <= 0:
        raise ValueError("El precio debe ser mayor que cero")
    if cuotas < 1 or int(cuotas) != cuotas:
        raise ValueError("Las cuotas deben ser un número entero de al menos 1")
    if not 0 <= descuento < 1:
        raise ValueError("El descuento debe estar entre 0 y 100 %")


def precio_de_contado(precio_lista: float, descuento: float = 0.0) -> float:
    """Precio pagando de contado; `descuento` va como proporción (0,10 = 10 %)."""
    _validar(precio_lista, 1, descuento)
    return precio_lista * (1 - descuento)


def tasa_mensual_de_tna(tna: float) -> float:
    """Lo que rinde un plazo fijo en 30 días, como proporción (misma cuenta que plazo_fijo)."""
    return plazo_fijo(1.0, tna, 30) - 1


def tna_de_tasa_mensual(tasa_mensual: float) -> float:
    """La TNA que corresponde a una tasa de 30 días."""
    return tasa_mensual * 365 / 30


def valor_presente_de_cuotas(precio_lista: float, cuotas: int, tasa_mensual: float) -> float:
    """Cuánto valen hoy las cuotas si tu plata rinde `tasa_mensual` por mes."""
    _validar(precio_lista, cuotas, 0.0)
    if tasa_mensual <= -1:
        raise ValueError("La tasa mensual debe ser mayor que -100 %")
    valor_cuota = precio_lista / cuotas
    return sum(
        valor_cuota / (1 + tasa_mensual) ** (MESES_HASTA_LA_PRIMERA_CUOTA + k) for k in range(int(cuotas))
    )


def tasa_de_equilibrio(precio_lista: float, cuotas: int, descuento: float) -> float:
    """Tasa mensual a la que da lo mismo pagar de contado (con descuento) o en cuotas.

    Es el costo implícito de renunciar al descuento: si tu plata rinde más que
    esto por mes, convienen las cuotas; si rinde menos, el contado. Sin
    descuento es 0: las cuotas convienen con cualquier rendimiento positivo.
    """
    _validar(precio_lista, cuotas, descuento)
    if descuento == 0:
        return 0.0
    objetivo = precio_lista * (1 - descuento)
    bajo, alto = 0.0, 1.0
    for _ in range(200):  # el valor presente baja hacia 0 cuando la tasa crece
        if valor_presente_de_cuotas(precio_lista, cuotas, alto) <= objetivo:
            break
        alto *= 2
    for _ in range(200):
        medio = (bajo + alto) / 2
        if valor_presente_de_cuotas(precio_lista, cuotas, medio) > objetivo:
            bajo = medio
        else:
            alto = medio
    return (bajo + alto) / 2
