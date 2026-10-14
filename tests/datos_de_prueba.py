"""Datos de prueba compartidos entre los tests."""

from datetime import datetime, timedelta, timezone

from simulador.ingesta.dolar import CotizacionActual

ZONA_AR = timezone(timedelta(hours=-3))


def niveles_mensuales(inicio: tuple[int, int], cantidad: int, variacion: float, base: float = 100.0):
    """Índice que sube `variacion` por mes, como lista de (fecha ISO, nivel)."""
    niveles = []
    anio, mes = inicio
    for i in range(cantidad):
        niveles.append((f"{anio:04d}-{mes:02d}-01", base * (1 + variacion) ** i))
        mes += 1
        if mes == 13:
            anio, mes = anio + 1, 1
    return niveles


# 20 meses (2025-01 a 2026-08) al 2 % mensual: interanual = 1,02^12 - 1 = 26,82 %.
IPC_20_MESES = niveles_mensuales((2025, 1), 20, 0.02)

# 7 meses (2026-01 a 2026-07) al 3 %: 6 variaciones acumulan 19,41 %.
IPC_7_MESES = niveles_mensuales((2026, 1), 7, 0.03)


def cotizaciones_blue(meses=range(1, 8)):
    """Blue de prueba como (fecha, compra, venta).

    Cada mes trae un día temprano con valores absurdos (1/1) y el cierre real el
    día 28, para verificar que se usa el último día del mes. Base: 1000 en enero,
    +100 por mes; compra = base - 10, venta = base + 10.
    """
    filas = []
    for mes in meses:
        base = 1000.0 + 100 * (mes - 1)
        filas.append((f"2026-{mes:02d}-10", 1.0, 1.0))
        filas.append((f"2026-{mes:02d}-28", base - 10, base + 10))
    return filas


def blue_actual(compra=1520.0, venta=1540.0, actualizado=None):
    """Cotización en vivo de prueba; por defecto, actualizada el 2026-10-13 a las 14:30."""
    if actualizado is None:
        actualizado = datetime(2026, 10, 13, 14, 30, tzinfo=ZONA_AR)
    return CotizacionActual(compra, venta, actualizado)


def cotizaciones_actuales(sin=()):
    """Cotizaciones en vivo de prueba por tipo de dólar, como las devuelve la fuente.

    Todas del 2026-10-13 a las 14:30, salvo el oficial, que quedó del viernes 9 a las 15:55.
    `sin` son las 'casas' que la fuente no trae.
    """
    ahora = datetime(2026, 10, 13, 14, 30, tzinfo=ZONA_AR)
    viernes = datetime(2026, 10, 9, 15, 55, tzinfo=ZONA_AR)
    datos = {
        "oficial": CotizacionActual(1485.0, 1535.0, viernes),
        "blue": CotizacionActual(1520.0, 1540.0, ahora),
        "bolsa": CotizacionActual(1535.9, 1542.9, ahora),
        "contadoconliqui": CotizacionActual(1605.5, 1606.6, ahora),
        "cripto": CotizacionActual(1605.97, 1610.17, ahora),
    }
    return {casa: cotizacion for casa, cotizacion in datos.items() if casa not in sin}
