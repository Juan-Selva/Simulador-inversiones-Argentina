"""Interfaz de línea de comandos."""

from __future__ import annotations

from typing import Callable, NoReturn, Optional, TypeVar

import typer

from simulador import servicio
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
from simulador.servicio import DolarHoy, ErrorSimulador

app = typer.Typer(help="Simulador de inversiones con datos argentinos.")

T = TypeVar("T")


def _salir(mensaje: str) -> NoReturn:
    typer.echo(mensaje, err=True)
    raise typer.Exit(code=1)


def _ejecutar(llamada: Callable[[], T]) -> T:
    try:
        return llamada()
    except ErrorSimulador as error:
        _salir(str(error))


def _mes(fecha_iso: str) -> str:
    return fecha_iso[:7]


def _linea_blue(dolar: DolarHoy) -> str:
    detalle = detalle_actualizacion(dolar.actualizado, dolar.fecha, dolar.es_de_hoy)
    return f"Dólar blue: compra {pesos(dolar.compra)} | venta {pesos(dolar.venta)} ({detalle})"


def _mostrar_blue(dolar: DolarHoy) -> None:
    typer.echo(_linea_blue(dolar))
    if not dolar.es_de_hoy:
        typer.echo(AVISO_BLUE_DESACTUALIZADO)


@app.callback()
def principal() -> None:
    """Simulador de inversiones con datos argentinos."""


@app.command("inflacion")
def inflacion_cmd(
    meses: int = typer.Option(12, help="Cantidad de meses a mostrar"),
) -> None:
    """Muestra la inflación mensual real de los últimos meses (INDEC, IPC nacional)."""
    datos = _ejecutar(lambda: servicio.inflacion_ultimos_meses(meses))
    for fecha, variacion in datos:
        typer.echo(f"{_mes(fecha)}  {pct(variacion)}")
    acumulada = inflacion_acumulada([v for _, v in datos])
    typer.echo(f"Acumulada en {meses} meses: {pct(acumulada)}")


@app.command("inflacion-mes")
def inflacion_mes_cmd(
    anio: Optional[int] = typer.Option(None, help="Año (ej: 2025)"),
    mes: Optional[int] = typer.Option(None, help="Mes, de 1 a 12"),
) -> None:
    """Inflación de un mes puntual. Sin opciones, la del mes pasado."""
    r = _ejecutar(lambda: servicio.consultar_inflacion_mes(anio, mes))
    if r.aviso:
        typer.echo(r.aviso)
    typer.echo(f"Inflación de {nombre_mes(r.mes)}: {pct(r.variacion)}")
    if r.interanual is not None:
        typer.echo(f"Interanual: {pct(r.interanual)}")


@app.command("dolar")
def dolar_cmd() -> None:
    """Muestra el valor del dólar blue de hoy."""
    d = _ejecutar(servicio.dolar_hoy)
    _mostrar_blue(d)
    typer.echo(f"Comprar un dólar cuesta {pesos(d.venta)}; venderlo paga {pesos(d.compra)}.")


@app.command("plazo-fijo")
def plazo_fijo_cmd(
    capital: float = typer.Option(..., help="Capital inicial en pesos"),
    tna: float = typer.Option(..., help="Tasa nominal anual, en porcentaje (ej: 35)"),
    meses: int = typer.Option(6, help="Cantidad de meses a simular"),
    inflacion_mensual: Optional[float] = typer.Option(
        None,
        help="Inflación mensual constante, en porcentaje (ej: 3.5). "
        "Si se omite, usa el IPC real del INDEC de los últimos meses.",
    ),
    renovar: bool = typer.Option(True, help="Renovar cada 30 días capitalizando intereses"),
) -> None:
    """Simula un plazo fijo y lo compara contra la inflación."""
    try:
        sim = servicio.calcular_plazo_fijo(capital, tna, meses, inflacion_mensual, renovar)
    except servicio.ErrorDeRed as error:
        _salir(f"{error} También podés pasar --inflacion-mensual para no depender de la descarga.")
    except ErrorSimulador as error:
        _salir(str(error))

    if sim.desde:
        typer.echo(f"Inflación real (INDEC, IPC nacional): {sim.desde} a {sim.hasta}")
    r = sim.resultado
    typer.echo(f"Capital inicial:        {pesos(r.capital_inicial)}")
    typer.echo(f"Monto final:            {pesos(r.monto_final)}")
    typer.echo(f"Rendimiento nominal:    {pct(r.rendimiento_nominal)}")
    typer.echo(f"Inflación acumulada:    {pct(r.inflacion_acumulada)}")
    typer.echo(f"Rendimiento real:       {pct(r.rendimiento_real)}")
    typer.echo(f"Monto final (pesos de hoy): {pesos(r.monto_final_real)}")


@app.command("comparar")
def comparar_cmd(
    capital: float = typer.Option(..., help="Capital inicial en pesos"),
    tna: float = typer.Option(..., help="TNA del plazo fijo, en porcentaje (ej: 35)"),
    meses: int = typer.Option(6, help="Cantidad de meses hacia atrás a simular"),
) -> None:
    """Compara plazo fijo contra dólar blue, usando la inflación real del INDEC."""
    c = _ejecutar(lambda: servicio.comparar_estrategias(capital, tna, meses))

    typer.echo(f"Período: {c.inicio} a {c.fin} ({c.meses} meses), inflación real del INDEC")
    typer.echo(
        f"Dólar blue (cierre de mes): comprás a {pesos(c.precio_compra)} (fin de {c.inicio}), "
        f"vendés a {pesos(c.precio_venta)} (fin de {c.fin})"
    )
    typer.echo("")
    typer.echo(f"{'Estrategia':<12}{'Nominal':>10}{'Real':>10}  Monto final (pesos de hoy)")
    for nombre, r in (("Plazo fijo", c.plazo_fijo), ("Dólar blue", c.dolar)):
        typer.echo(
            f"{nombre:<12}{pct(r.rendimiento_nominal):>10}{pct(r.rendimiento_real):>10}"
            f"  {pesos(r.monto_final_real)}"
        )
    typer.echo(f"Inflación acumulada: {pct(c.plazo_fijo.inflacion_acumulada)}")
    typer.echo(f"Mejor en términos reales: {c.mejor}")
    typer.echo("")
    _mostrar_blue(c.blue_hoy)
    typer.echo("Resultado histórico: no predice rendimientos futuros.")


@app.command("comprar-dolares")
def comprar_dolares_cmd(
    pesos_a_gastar: float = typer.Option(..., "--pesos", help="Monto en pesos con el que querés comprar dólares"),
    comision_broker: float = typer.Option(
        0.0, help="Comisión del broker para MEP y CCL, en porcentaje (ej: 0.3)"
    ),
) -> None:
    """Compara las formas de comprar dólares en Argentina, con impuestos y cargos."""
    c = _ejecutar(lambda: servicio.comprar_dolares(pesos_a_gastar, comision_broker))

    mejor = c.mas_barata
    typer.echo(
        f"Con {pesos(c.pesos)} la opción más barata es {mejor.nombre}: conseguís {dolares(mejor.dolares)} "
        f"a {pesos(mejor.precio_efectivo)} cada uno."
    )
    typer.echo("")
    typer.echo(f"{'Opción':<28}{'Precio final':>16}{'Dólares':>16}  Frente a la más barata")
    for o in c.opciones:
        frente = "la más barata" if o is mejor else f"+{pct(o.sobreprecio)}"
        if not o.para_ahorrar:
            frente += " (solo para pagar)"
        typer.echo(f"{o.nombre:<28}{pesos(o.precio_efectivo):>16}{dolares(o.dolares):>16}  {frente}")
    for o in c.opciones:
        typer.echo("")
        typer.echo(o.nombre)
        detalle = detalle_actualizacion(o.actualizado, o.fecha, o.es_de_hoy)
        typer.echo(f"  - Cotización de venta {pesos(o.precio)}, {detalle}.")
        if o.cargos:
            for cargo in o.cargos:
                typer.echo(f"  - Se suma: {cargo.nombre}, {pct(cargo.tasa)}.")
        else:
            typer.echo("  - Sin impuestos ni cargos incluidos en el precio.")
        for nota in o.notas:
            typer.echo(f"  - {nota}")
    typer.echo("")
    typer.echo(AVISO_COTIZACIONES)
    typer.echo(aviso_normas(c.reglas_al))
    if c.sin_cotizacion:
        typer.echo("Sin cotización de la fuente para: " + ", ".join(c.sin_cotizacion) + ".")


if __name__ == "__main__":
    app()
