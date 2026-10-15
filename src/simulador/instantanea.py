"""Foto de una simulación, lista para guardarla en el historial.

Una instantánea junta tres cosas tal como estaban en el momento de simular:
los parámetros que ingresó el usuario, los datos crudos del resultado y el
texto que se mostró en pantalla (con las cotizaciones, UVA e inflación de ese
día). Mostrar una simulación guardada es mostrar ese texto: no se vuelve a
calcular con datos de hoy.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from simulador.formato import (
    AVISO_BLUE_DESACTUALIZADO,
    AVISO_COTIZACIONES,
    NOTA_SIN_DESCUENTO,
    SUPUESTOS_CUOTAS,
    aviso_normas,
    detalle_actualizacion,
    dolares,
    nombre_mes,
    numero,
    pct,
    pesos,
)
from simulador.servicio import Comparacion, ComparacionCuotas, CompraDeDolares, PlazoFijoSimulado

PLAZO_FIJO = "plazo_fijo"
COMPARACION = "comparacion"
COMPRA_DOLARES = "compra_dolares"
CONTADO_CUOTAS = "contado_cuotas"

NOMBRES_DE_TIPO = {
    PLAZO_FIJO: "Plazo fijo",
    COMPARACION: "Comparación de estrategias",
    COMPRA_DOLARES: "Compra de dólares",
    CONTADO_CUOTAS: "Contado o cuotas",
}


@dataclass(frozen=True)
class Instantanea:
    tipo: str
    parametros: dict[str, Any]
    datos: dict[str, Any]
    texto: list[str]


def a_json(valor: Any) -> Any:
    """Convierte dataclasses, tuplas y fechas en estructuras que entran en JSON."""
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {campo.name: a_json(getattr(valor, campo.name)) for campo in dataclasses.fields(valor)}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, datetime):
        return valor.isoformat()
    return valor


def _linea_resultado(nombre: str, r) -> str:
    return (
        f"{nombre}: nominal {pct(r.rendimiento_nominal)}, real {pct(r.rendimiento_real)}, "
        f"monto final {pesos(r.monto_final_real)} (en pesos de hoy)"
    )


def de_plazo_fijo(
    capital: float,
    tna: float,
    meses: int,
    inflacion_mensual: float | None,
    renovar: bool,
    sim: PlazoFijoSimulado,
) -> Instantanea:
    r = sim.resultado
    if sim.desde:
        inflacion = f"Inflación real del INDEC: {nombre_mes(sim.desde)} a {nombre_mes(sim.hasta)}."
    else:
        inflacion = f"Inflación mensual constante ingresada a mano: {pct(inflacion_mensual / 100)}."
    texto = [
        f"Capital {pesos(capital)}, TNA {pct(tna / 100)}, {meses} meses, "
        + ("renovando cada 30 días." if renovar else "sin renovar."),
        inflacion,
        f"Monto final: {pesos(r.monto_final)}",
        f"Rendimiento nominal: {pct(r.rendimiento_nominal)}",
        f"Inflación acumulada: {pct(r.inflacion_acumulada)}",
        f"Rendimiento real: {pct(r.rendimiento_real)}",
        f"Monto final (pesos de hoy): {pesos(r.monto_final_real)}",
    ]
    parametros = {
        "capital": capital,
        "tna": tna,
        "meses": meses,
        "inflacion_mensual": inflacion_mensual,
        "renovar": renovar,
    }
    return Instantanea(PLAZO_FIJO, parametros, a_json(sim), texto)


def de_comparacion(capital: float, tna: float, meses: int, c: Comparacion) -> Instantanea:
    texto = [
        f"Capital {pesos(capital)}, TNA {pct(tna / 100)}, {meses} meses.",
        f"Período: {nombre_mes(c.inicio)} a {nombre_mes(c.fin)}, inflación real del INDEC.",
        f"Dólar blue (cierre de mes): comprás a {pesos(c.precio_compra)} (fin de {nombre_mes(c.inicio)}) "
        f"y vendés a {pesos(c.precio_venta)} (fin de {nombre_mes(c.fin)}).",
    ]
    if c.uva is not None:
        texto.append(
            f"UVA (cierre de mes): {numero(c.uva_inicial)} (fin de {nombre_mes(c.inicio)}) "
            f"a {numero(c.uva_final)} (fin de {nombre_mes(c.fin)})."
        )
    texto.append(f"Inflación acumulada del período: {pct(c.plazo_fijo.inflacion_acumulada)}.")
    texto.append(_linea_resultado("Plazo fijo", c.plazo_fijo))
    texto.append(_linea_resultado("Dólar blue", c.dolar))
    if c.uva is not None:
        texto.append(_linea_resultado("Plazo fijo UVA", c.uva))
    texto.append(f"Mejor en términos reales: {c.mejor}.")
    if c.aviso_uva:
        texto.append(c.aviso_uva)
    detalle = detalle_actualizacion(c.blue_hoy.actualizado, c.blue_hoy.fecha, c.blue_hoy.es_de_hoy)
    texto.append(
        f"Dólar blue al simular: compra {pesos(c.blue_hoy.compra)} | venta {pesos(c.blue_hoy.venta)} ({detalle})."
    )
    if not c.blue_hoy.es_de_hoy:
        texto.append(AVISO_BLUE_DESACTUALIZADO)
    parametros = {"capital": capital, "tna": tna, "meses": meses}
    return Instantanea(COMPARACION, parametros, {**a_json(c), "mejor": c.mejor}, texto)


def de_compra_dolares(comision_broker: float, c: CompraDeDolares) -> Instantanea:
    mejor = c.mas_barata
    texto = [
        f"Monto {pesos(c.pesos)}, comisión del broker {pct(comision_broker / 100)}.",
        f"La opción más barata es {mejor.nombre}: {dolares(mejor.dolares)} a {pesos(mejor.precio_efectivo)} cada uno.",
    ]
    for o in c.opciones:
        frente = "la más barata" if o is mejor else f"+{pct(o.sobreprecio)} frente a la más barata"
        if not o.para_ahorrar:
            frente += ", solo para pagar"
        texto.append(
            f"{o.nombre}: cotización de venta {pesos(o.precio)} "
            f"({detalle_actualizacion(o.actualizado, o.fecha, o.es_de_hoy)}), "
            f"precio final {pesos(o.precio_efectivo)}, {dolares(o.dolares)} ({frente})."
        )
        for cargo in o.cargos:
            texto.append(f"    Se suma: {cargo.nombre}, {pct(cargo.tasa)}.")
    texto.append(AVISO_COTIZACIONES)
    texto.append(aviso_normas(c.reglas_al))
    if c.sin_cotizacion:
        texto.append("Sin cotización de la fuente para: " + ", ".join(c.sin_cotizacion) + ".")
    parametros = {"pesos": c.pesos, "comision_broker": comision_broker}
    return Instantanea(COMPRA_DOLARES, parametros, {**a_json(c), "mas_barata": mejor.clave}, texto)


def de_contado_cuotas(
    precio: float,
    cuotas: int,
    tna: float,
    descuento: float,
    inflacion_mensual: float | None,
    c: ComparacionCuotas,
) -> Instantanea:
    texto = [
        f"Precio en cuotas: {pesos(c.precio_lista)}",
        f"Cuotas: {c.cuotas} de {pesos(c.valor_cuota)}",
    ]
    if c.descuento > 0:
        texto.append(f"Precio de contado: {pesos(c.precio_contado)} ({pct(c.descuento)} de descuento)")
        texto.append(
            f"Pagar en cuotas equivale a un crédito al {pct(c.tasa_equilibrio)} por mes "
            f"(TNA {pct(c.tna_equivalente)})"
        )
    else:
        texto.append(f"Precio de contado: {pesos(c.precio_contado)} (sin descuento)")
    texto.append("Valor de las cuotas hoy, según cómo rinda tu plata:")
    for e in [c.plazo_fijo] + ([c.inflacion] if c.inflacion else []):
        if e.mejor == "En cuotas":
            conviene = f"conviene pagar en cuotas (ahorrás {pesos(e.ahorro)})"
        elif e.mejor == "De contado":
            conviene = f"conviene pagar de contado (ahorrás {pesos(-e.ahorro)})"
        else:
            conviene = "da lo mismo"
        texto.append(f"    {e.nombre}: {pesos(e.valor_presente)} -> {conviene}")
    texto.append(f"Resultado con tu plazo fijo: {c.mejor}")
    if c.descuento == 0:
        texto.append(NOTA_SIN_DESCUENTO)
    texto.append(SUPUESTOS_CUOTAS)
    if c.aviso:
        texto.append(c.aviso)
    parametros = {
        "precio": precio,
        "cuotas": cuotas,
        "tna": tna,
        "descuento": descuento,
        "inflacion_mensual": inflacion_mensual,
    }
    return Instantanea(CONTADO_CUOTAS, parametros, {**a_json(c), "mejor": c.mejor}, texto)
