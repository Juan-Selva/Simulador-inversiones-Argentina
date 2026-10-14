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
from simulador.servicio import (
    Comparacion,
    ComparacionCuotas,
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
    lineas = [
        f"Período: {nombre_mes(c.inicio)} a {nombre_mes(c.fin)} ({c.meses} meses), inflación real del INDEC",
        f"Dólar blue (cierre de mes): comprás a {pesos(c.precio_compra)} "
        f"(fin de {nombre_mes(c.inicio)}) y vendés a {pesos(c.precio_venta)} (fin de {nombre_mes(c.fin)})",
    ]
    if c.uva is not None:
        lineas.append(
            f"UVA (cierre de mes): {numero(c.uva_inicial)} (fin de {nombre_mes(c.inicio)}) "
            f"a {numero(c.uva_final)} (fin de {nombre_mes(c.fin)})"
        )
    lineas.append(f"Inflación acumulada del período: {pct(c.plazo_fijo.inflacion_acumulada)}")
    return lineas


def filas_comparacion(c: Comparacion) -> list[list[Celda]]:
    filas = []
    estrategias = [("Plazo fijo", c.plazo_fijo), ("Dólar blue", c.dolar)]
    if c.uva is not None:
        estrategias.append(("Plazo fijo UVA", c.uva))
    for nombre, r in estrategias:
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


# Íconos del selector de tema (sol y luna) y el modo que entiende la interfaz.
# Son símbolos simples que se dibujan con cualquier fuente del sistema.
TEMAS = {"☀": "light", "☾": "dark"}


def etiqueta_de_tema(modo: str) -> str:
    """'dark' -> '☾'. Un modo que no es ni claro ni oscuro se muestra como claro."""
    for etiqueta, valor in TEMAS.items():
        if valor == modo:
            return etiqueta
    return next(iter(TEMAS))


# --- contado o cuotas ---------------------------------------------------------

CABECERA_CUOTAS = ["Si tu plata rinde como", "Las cuotas valen hoy", "Conviene"]


def filas_cuotas(c: ComparacionCuotas) -> list[tuple[str, Celda]]:
    filas = [
        ("Precio en cuotas", Celda(pesos(c.precio_lista))),
        ("Cuotas", Celda(f"{c.cuotas} de {pesos(c.valor_cuota)}")),
    ]
    if c.descuento > 0:
        filas.append(("Precio de contado", Celda(f"{pesos(c.precio_contado)} ({pct(c.descuento)} de descuento)")))
        filas.append(
            (
                "Pagar en cuotas equivale a un crédito al",
                Celda(f"{pct(c.tasa_equilibrio)} por mes (TNA {pct(c.tna_equivalente)})"),
            )
        )
    else:
        filas.append(("Precio de contado", Celda(f"{pesos(c.precio_contado)} (sin descuento)")))
    return filas


def _conviene(escenario) -> str:
    if escenario.mejor == "En cuotas":
        return f"En cuotas (ahorrás {pesos(escenario.ahorro)})"
    if escenario.mejor == "De contado":
        return f"De contado (ahorrás {pesos(-escenario.ahorro)})"
    return "Da lo mismo"


def filas_escenarios_cuotas(c: ComparacionCuotas) -> list[list[Celda]]:
    escenarios = [c.plazo_fijo] + ([c.inflacion] if c.inflacion else [])
    return [
        [Celda(e.nombre), Celda(pesos(e.valor_presente)), Celda(_conviene(e))] for e in escenarios
    ]


def veredicto_cuotas(c: ComparacionCuotas) -> str:
    e = c.plazo_fijo
    if e.mejor == "En cuotas":
        return f"Conviene pagar en cuotas: con tu plata en el plazo fijo ahorrás {pesos(e.ahorro)} en pesos de hoy."
    if e.mejor == "De contado":
        return (
            f"Conviene pagar de contado: ahorrás {pesos(-e.ahorro)} en pesos de hoy "
            "frente a dejar la plata en el plazo fijo."
        )
    return "Da lo mismo pagar de contado o en cuotas si tu plata queda en el plazo fijo."


def notas_cuotas(c: ComparacionCuotas) -> list[str]:
    notas = []
    if c.descuento == 0:
        notas.append(NOTA_SIN_DESCUENTO)
    notas.append(SUPUESTOS_CUOTAS)
    if c.aviso:
        notas.append(c.aviso)
    return notas
