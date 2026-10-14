"""Presentación de los resultados del servicio como texto listo para mostrar.

Sin dependencias de interfaz gráfica: las pantallas solo tienen que dibujar
estas celdas y filas.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulador.dominio.estrategias import inflacion_acumulada
from simulador.formato import (
    AVISO_BLUE_DESACTUALIZADO,
    AVISO_COTIZACIONES,
    aviso_normas,
    detalle_actualizacion,
    dolares,
    nombre_mes,
    pct,
    pesos,
)
from simulador.servicio import (
    Comparacion,
    CompraDeDolares,
    DolarHoy,
    InflacionDeUnMes,
    OpcionDeCompra,
    PlazoFijoSimulado,
)


@dataclass(frozen=True)
class Celda:
    texto: str
    tono: str = "normal"  # "normal", "positivo" o "negativo"


def tono_de(valor: float) -> str:
    """Verde si el valor es positivo, rojo si es negativo (según cómo se muestra, con 2 decimales)."""
    redondeado = round(valor * 100, 2)
    if redondeado > 0:
        return "positivo"
    if redondeado < 0:
        return "negativo"
    return "normal"


def _porcentaje(valor: float) -> Celda:
    return Celda(pct(valor), tono_de(valor))


def tarjeta_blue(dolar: DolarHoy) -> tuple[str, str]:
    """(valores, detalle) para la tarjeta del dólar blue."""
    valores = f"Compra {pesos(dolar.compra)}  |  Venta {pesos(dolar.venta)}"
    detalle = detalle_actualizacion(dolar.actualizado, dolar.fecha, dolar.es_de_hoy)
    return valores, detalle[0].upper() + detalle[1:]


def aviso_blue(dolar: DolarHoy) -> str | None:
    """Advertencia cuando el dato no se actualizó hoy."""
    return None if dolar.es_de_hoy else AVISO_BLUE_DESACTUALIZADO


def periodo_plazo_fijo(sim: PlazoFijoSimulado) -> str:
    if sim.desde:
        return f"Inflación real del INDEC: {nombre_mes(sim.desde)} a {nombre_mes(sim.hasta)}"
    return "Inflación mensual constante, ingresada a mano"


def filas_plazo_fijo(sim: PlazoFijoSimulado) -> list[tuple[str, Celda]]:
    r = sim.resultado
    return [
        ("Capital inicial", Celda(pesos(r.capital_inicial))),
        ("Monto final", Celda(pesos(r.monto_final))),
        ("Rendimiento nominal", _porcentaje(r.rendimiento_nominal)),
        ("Inflación acumulada", Celda(pct(r.inflacion_acumulada))),
        ("Rendimiento real", _porcentaje(r.rendimiento_real)),
        ("Monto final (pesos de hoy)", Celda(pesos(r.monto_final_real))),
    ]


CABECERA_COMPARACION = ["Estrategia", "Nominal", "Real", "Monto final (pesos de hoy)"]


def resumen_comparacion(c: Comparacion) -> list[str]:
    return [
        f"Período: {nombre_mes(c.inicio)} a {nombre_mes(c.fin)} ({c.meses} meses), inflación real del INDEC",
        f"Dólar blue (cierre de mes): comprás a {pesos(c.precio_compra)} "
        f"(fin de {nombre_mes(c.inicio)}) y vendés a {pesos(c.precio_venta)} (fin de {nombre_mes(c.fin)})",
        f"Inflación acumulada del período: {pct(c.plazo_fijo.inflacion_acumulada)}",
    ]


def filas_comparacion(c: Comparacion) -> list[list[Celda]]:
    filas = []
    for nombre, r in (("Plazo fijo", c.plazo_fijo), ("Dólar blue", c.dolar)):
        filas.append(
            [
                Celda(nombre),
                _porcentaje(r.rendimiento_nominal),
                _porcentaje(r.rendimiento_real),
                Celda(pesos(r.monto_final_real)),
            ]
        )
    return filas


def veredicto(c: Comparacion) -> str:
    return f"Mejor en términos reales: {c.mejor}"


def filas_inflacion_mes(r: InflacionDeUnMes) -> list[tuple[str, Celda]]:
    filas = [(f"Inflación de {nombre_mes(r.mes)}", Celda(pct(r.variacion)))]
    if r.interanual is not None:
        filas.append(("Interanual", Celda(pct(r.interanual))))
    return filas


def filas_inflacion_meses(datos: list[tuple[str, float]]) -> list[list[Celda]]:
    """Una fila por mes y, al final, la inflación acumulada del período."""
    filas = [[Celda(nombre_mes(fecha).capitalize()), Celda(pct(variacion))] for fecha, variacion in datos]
    acumulada = inflacion_acumulada([v for _, v in datos])
    filas.append([Celda(f"Acumulada en {len(datos)} meses"), Celda(pct(acumulada))])
    return filas


CABECERA_COMPRA = ["Opción", "Cargos", "Precio final por USD", "Dólares", "Frente a la más barata"]

def resumen_compra(c: CompraDeDolares) -> str:
    mejor = c.mas_barata
    return (
        f"Con {pesos(c.pesos)} la opción más barata es {mejor.nombre}: conseguís {dolares(mejor.dolares)} "
        f"a {pesos(mejor.precio_efectivo)} cada uno."
    )


def _cargos_totales(o: OpcionDeCompra) -> str:
    total = sum(cargo.tasa for cargo in o.cargos)
    return pct(total) if o.cargos else "Ninguno"


def _frente_a_la_mas_barata(o: OpcionDeCompra, es_la_mas_barata: bool) -> Celda:
    if es_la_mas_barata:
        return Celda("La más barata", "positivo")
    if not o.para_ahorrar:
        return Celda(f"+{pct(o.sobreprecio)} (solo para pagar)", "negativo")
    return Celda(f"+{pct(o.sobreprecio)}", "negativo" if round(o.sobreprecio * 100, 2) > 0 else "normal")


def filas_compra(c: CompraDeDolares) -> list[list[Celda]]:
    mejor = c.mas_barata
    return [
        [
            Celda(o.nombre),
            Celda(_cargos_totales(o)),
            Celda(pesos(o.precio_efectivo)),
            Celda(dolares(o.dolares)),
            _frente_a_la_mas_barata(o, o is mejor),
        ]
        for o in c.opciones
    ]


def detalle_compra(o: OpcionDeCompra) -> list[str]:
    """Líneas de detalle de una opción: de cuándo es la cotización, cargos y condiciones."""
    actualizacion = detalle_actualizacion(o.actualizado, o.fecha, o.es_de_hoy)
    lineas = [f"Cotización de venta {pesos(o.precio)}, {actualizacion}."]
    if o.cargos:
        lineas.extend(f"Se suma: {cargo.nombre}, {pct(cargo.tasa)}." for cargo in o.cargos)
    else:
        lineas.append("Sin impuestos ni cargos incluidos en el precio.")
    lineas.extend(o.notas)
    return lineas


def pie_compra(c: CompraDeDolares) -> list[str]:
    lineas = [AVISO_COTIZACIONES, aviso_normas(c.reglas_al)]
    if c.sin_cotizacion:
        lineas.append("Sin cotización de la fuente para: " + ", ".join(c.sin_cotizacion) + ".")
    return lineas
