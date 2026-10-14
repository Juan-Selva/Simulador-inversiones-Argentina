"""Formato de números y fechas para mostrar al usuario (CLI e interfaces)."""

from __future__ import annotations

from datetime import datetime

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)


def pesos(valor: float) -> str:
    """1234567.891 -> '$ 1.234.567,89'."""
    return f"$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def numero(valor: float) -> str:
    """Número con formato argentino (1.800,05)."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(valor: float) -> str:
    """0.1855 -> '18,55 %'."""
    return f"{valor * 100:.2f} %".replace(".", ",")


def dolares(valor: float) -> str:
    """645.1234 -> 'USD 645,12'."""
    return f"USD {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def nombre_mes(mes_iso: str) -> str:
    """'2026-08' o '2026-08-01' -> 'agosto de 2026'."""
    anio, mes = int(mes_iso[:4]), int(mes_iso[5:7])
    return f"{MESES[mes - 1]} de {anio}"


AVISO_BLUE_DESACTUALIZADO = "Este dato puede no reflejar la cotización de este momento."


def detalle_actualizacion(actualizado: datetime | None, fecha: str, es_de_hoy: bool) -> str:
    """Texto que dice qué tan fresco es un dato, para mostrar junto a la cotización."""
    if actualizado is None:
        return f"último cierre diario del {fecha}, sin hora informada"
    hora = actualizado.strftime("%H:%M")
    if es_de_hoy:
        return f"actualizado hoy a las {hora}"
    return f"actualizado el {actualizado.strftime('%d/%m')} a las {hora}"


AVISO_COTIZACIONES = (
    "Las cotizaciones vienen de DolarAPI, una fuente comunitaria, y pueden tardar en reflejar el mercado; "
    "el dólar oficial solo se actualiza en horario bancario."
)


def aviso_normas(fecha: str) -> str:
    return (
        f"Normas e impuestos relevados al {fecha}: verificalos antes de operar. "
        "No es asesoramiento financiero ni impositivo."
    )


NOTA_SIN_DESCUENTO = (
    "Sin descuento por pagar de contado, las cuotas sin interés siempre convienen: "
    "pagás lo mismo, pero más tarde."
)

SUPUESTOS_CUOTAS = (
    "Supone que la primera cuota se paga a los 30 días y las demás una por mes, y que la plata que no gastás "
    "hoy rinde la tasa indicada. Los montos están en pesos de hoy y no incluyen comisiones ni intereses por "
    "pagar tarde el resumen de la tarjeta."
)
