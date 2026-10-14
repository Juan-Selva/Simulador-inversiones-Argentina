"""Casos de uso del simulador.

Combinan la ingesta de datos con el dominio. Los usan la CLI y las interfaces
gráficas, así que no imprimen nada ni dependen de Typer: devuelven datos o
levantan ErrorSimulador con un mensaje listo para mostrar. Las tasas que
reciben (TNA, inflación mensual) van en porcentaje: 35 significa 35 %.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import httpx

from simulador.dominio.compra_dolares import (
    CANALES,
    REGLAS_RELEVADAS,
    Cargo,
    cargos_del_canal,
    dolares_obtenidos,
    precio_efectivo,
)
from simulador.dominio.cuotas import (
    precio_de_contado,
    tasa_de_equilibrio,
    tasa_mensual_de_tna,
    tna_de_tasa_mensual,
    valor_presente_de_cuotas,
)
from simulador.dominio.estrategias import Resultado, simular_dolar, simular_plazo_fijo, simular_uva
from simulador.formato import nombre_mes, pct
from simulador.ingesta.uva import cierres_mensuales as cierres_uva
from simulador.ingesta.uva import descargar_uva
from simulador.ingesta.dolar import (
    Cotizacion,
    CotizacionActual,
    cierres_mensuales,
    descargar_blue,
    descargar_blue_actual,
    descargar_cotizaciones_actuales,
)
from simulador.ingesta.series import (
    IPC_NIVEL_GENERAL,
    descargar_serie,
    mes_anterior,
    mes_pasado,
    ultimas_variaciones,
    ultimo_mes,
    valor_del_mes,
    variacion_del_mes,
    variacion_interanual,
)


class ErrorSimulador(Exception):
    """Problema esperable (datos, parámetros), con un mensaje apto para el usuario."""


class ErrorDeRed(ErrorSimulador):
    """No se pudo descargar un dato de una API externa."""


def _hoy() -> date:
    return date.today()


@dataclass(frozen=True)
class InflacionDeUnMes:
    mes: str  # AAAA-MM
    variacion: float
    interanual: float | None
    aviso: str | None = None


@dataclass(frozen=True)
class DolarHoy:
    compra: float  # precio al que el mercado te compra un dólar (lo que recibís al vender)
    venta: float  # precio al que el mercado te vende un dólar (lo que pagás al comprar)
    actualizado: datetime | None  # cuándo actualizó la fuente el dato (None si no lo informa)
    fecha: str  # AAAA-MM-DD del dato
    es_de_hoy: bool  # True solo si la fuente se actualizó hoy


@dataclass(frozen=True)
class PlazoFijoSimulado:
    resultado: Resultado
    desde: str | None  # primer mes de inflación usado (None si la inflación fue manual)
    hasta: str | None


@dataclass(frozen=True)
class Comparacion:
    inicio: str  # mes en cuyo cierre se compran los dólares
    fin: str  # mes en cuyo cierre se venden
    meses: int
    precio_compra: float
    precio_venta: float
    plazo_fijo: Resultado
    dolar: Resultado
    blue_hoy: DolarHoy
    uva: Resultado | None = None  # None si no se pudo simular (ver aviso_uva)
    uva_inicial: float | None = None
    uva_final: float | None = None
    aviso_uva: str | None = None

    @property
    def mejor(self) -> str:
        opciones = [("Plazo fijo", self.plazo_fijo), ("Dólar blue", self.dolar)]
        if self.uva is not None:
            opciones.append(("Plazo fijo UVA", self.uva))
        # max se queda con la primera ante empate: el orden de la lista desempata.
        return max(opciones, key=lambda o: o[1].rendimiento_real)[0]


def _cargar_ipc() -> list[tuple[str, float]]:
    try:
        return descargar_serie(IPC_NIVEL_GENERAL)
    except httpx.HTTPError as error:
        raise ErrorDeRed(
            f"No se pudo descargar el IPC del INDEC ({error}). Probá de nuevo más tarde."
        ) from error
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ErrorSimulador(
            f"La API del INDEC devolvió datos en un formato inesperado ({error!r})."
        ) from error


def _cargar_blue() -> list[Cotizacion]:
    try:
        return descargar_blue()
    except httpx.HTTPError as error:
        raise ErrorDeRed(
            f"No se pudo descargar el dólar blue ({error}). Probá de nuevo más tarde."
        ) from error
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ErrorSimulador(
            f"La API devolvió datos del dólar en un formato inesperado ({error!r})."
        ) from error


MESES_MINIMOS_UVA = 3  # los plazos fijos UVA tienen un plazo mínimo de 90 días


def _simular_uva(capital: float, inicio: str, fin: str, meses: int, inflacion: float) -> dict:
    """Campos de `Comparacion` para el plazo fijo UVA; si no se puede, explica por qué."""
    vacio = {"uva": None, "uva_inicial": None, "uva_final": None}
    if meses < MESES_MINIMOS_UVA:
        return {**vacio, "aviso_uva": "Plazo fijo UVA no incluido: exige un plazo mínimo de 90 días (3 meses)."}
    try:
        cierres = cierres_uva(descargar_uva())
        uva_inicial = valor_del_mes(cierres, inicio)
        uva_final = valor_del_mes(cierres, fin)
        resultado = simular_uva(capital, uva_inicial, uva_final, inflacion)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError) as error:
        return {**vacio, "aviso_uva": f"Plazo fijo UVA no incluido: no se pudo obtener la UVA ({error})."}
    return {"uva": resultado, "uva_inicial": uva_inicial, "uva_final": uva_final, "aviso_uva": None}


def _validar(capital: float, tna: float, meses: int) -> None:
    if capital <= 0:
        raise ErrorSimulador("El capital debe ser mayor que cero")
    if tna < 0:
        raise ErrorSimulador("La tasa no puede ser negativa")
    if meses < 1:
        raise ErrorSimulador("Los meses deben ser al menos 1")


def inflacion_ultimos_meses(meses: int) -> list[tuple[str, float]]:
    """Variación mensual del IPC de los últimos `meses` meses, como (fecha, variación)."""
    niveles = _cargar_ipc()
    try:
        return ultimas_variaciones(niveles, meses)
    except ValueError as error:
        raise ErrorSimulador(str(error)) from error


def consultar_inflacion_mes(anio: int | None = None, mes: int | None = None) -> InflacionDeUnMes:
    """Inflación de un mes puntual; sin parámetros, la del mes pasado.

    El INDEC publica con casi un mes de retraso: si la inflación del mes pasado
    todavía no salió, se devuelve la del último mes publicado con un aviso.
    """
    niveles = _cargar_ipc()
    if not niveles:
        raise ErrorSimulador("La API no devolvió datos del IPC")
    ultimo = ultimo_mes(niveles)
    aviso = None

    if anio is None and mes is None:
        objetivo = mes_pasado(_hoy())
        if objetivo > ultimo:
            aviso = (
                f"El INDEC todavía no publicó la inflación de {nombre_mes(objetivo)}; "
                "se muestra el último mes disponible."
            )
            objetivo = ultimo
    elif anio is None or mes is None:
        raise ErrorSimulador("Indicá el año y el mes juntos")
    else:
        if not 1 <= mes <= 12:
            raise ErrorSimulador("El mes debe estar entre 1 y 12")
        if anio < 1:
            raise ErrorSimulador("El año no es válido")
        objetivo = f"{anio:04d}-{mes:02d}"
        if objetivo > ultimo:
            raise ErrorSimulador(
                f"El INDEC todavía no publicó la inflación de {nombre_mes(objetivo)}. "
                f"El último mes publicado es {nombre_mes(ultimo)}."
            )

    try:
        variacion = variacion_del_mes(niveles, objetivo)
    except ValueError:
        raise ErrorSimulador(f"No hay datos de inflación para {nombre_mes(objetivo)}.") from None
    try:
        interanual = variacion_interanual(niveles, objetivo)
    except ValueError:
        interanual = None
    return InflacionDeUnMes(objetivo, variacion, interanual, aviso)


def _dolar_desde_historial(cotizaciones: list[Cotizacion]) -> DolarHoy:
    """Respaldo: último registro diario del historial.

    No informa la hora, y ese registro puede estar fechado hoy con el valor de
    ayer, así que nunca se marca como de hoy.
    """
    if not cotizaciones:
        raise ErrorSimulador("La API no devolvió cotizaciones del dólar blue")
    fecha, compra, venta = cotizaciones[-1]
    return DolarHoy(compra, venta, None, fecha, False)


def _blue_de_hoy(cotizaciones: list[Cotizacion] | None = None) -> DolarHoy:
    try:
        actual = descargar_blue_actual()
    except (httpx.HTTPError, KeyError, TypeError, ValueError, AttributeError):
        historial = cotizaciones if cotizaciones is not None else _cargar_blue()
        return _dolar_desde_historial(historial)
    dia = actual.actualizado.date()
    return DolarHoy(actual.compra, actual.venta, actual.actualizado, dia.isoformat(), dia == _hoy())


def dolar_hoy() -> DolarHoy:
    """Última cotización del dólar blue, con la hora en que la fuente la actualizó."""
    return _blue_de_hoy()


def calcular_plazo_fijo(
    capital: float,
    tna: float,
    meses: int,
    inflacion_mensual: float | None = None,
    renovar: bool = True,
) -> PlazoFijoSimulado:
    """Plazo fijo contra la inflación real del INDEC o contra una inflación mensual fija."""
    _validar(capital, tna, meses)
    if inflacion_mensual is None:
        datos = inflacion_ultimos_meses(meses)
        variaciones = [v for _, v in datos]
        desde, hasta = datos[0][0][:7], datos[-1][0][:7]
    else:
        variaciones = [inflacion_mensual / 100] * meses
        desde = hasta = None
    resultado = simular_plazo_fijo(capital, tna / 100, variaciones, renovar=renovar)
    return PlazoFijoSimulado(resultado, desde, hasta)


def comparar_estrategias(capital: float, tna: float, meses: int) -> Comparacion:
    """Plazo fijo, dólar blue y plazo fijo UVA en los últimos `meses` meses con inflación publicada."""
    _validar(capital, tna, meses)
    datos = inflacion_ultimos_meses(meses)
    variaciones = [v for _, v in datos]
    inicio = mes_anterior(datos[0][0])
    fin = datos[-1][0][:7]

    cotizaciones = _cargar_blue()
    try:
        # Se compra al precio de venta del mercado y se vende al precio de compra.
        precio_compra = valor_del_mes(cierres_mensuales(cotizaciones, "venta"), inicio)
        precio_venta = valor_del_mes(cierres_mensuales(cotizaciones, "compra"), fin)
        plazo = simular_plazo_fijo(capital, tna / 100, variaciones)
        dolar = simular_dolar(capital, precio_compra, precio_venta, plazo.inflacion_acumulada)
    except ValueError as error:
        raise ErrorSimulador(str(error)) from error

    return Comparacion(
        inicio=inicio,
        fin=fin,
        meses=meses,
        precio_compra=precio_compra,
        precio_venta=precio_venta,
        plazo_fijo=plazo,
        dolar=dolar,
        blue_hoy=_blue_de_hoy(cotizaciones),
        **_simular_uva(capital, inicio, fin, meses, plazo.inflacion_acumulada),
    )


@dataclass(frozen=True)
class OpcionDeCompra:
    clave: str
    nombre: str
    precio: float  # cotización de venta de la fuente, sin cargos
    actualizado: datetime  # cuándo actualizó la fuente este dato
    fecha: str  # AAAA-MM-DD del dato
    es_de_hoy: bool
    cargos: tuple[Cargo, ...]
    precio_efectivo: float  # pesos por dólar con los cargos incluidos
    dolares: float  # dólares que se consiguen con el monto
    sobreprecio: float  # cuánto más cara es que la opción más barata para ahorrar (0,01 = 1 %)
    notas: tuple[str, ...]
    para_ahorrar: bool


@dataclass(frozen=True)
class CompraDeDolares:
    pesos: float
    opciones: tuple[OpcionDeCompra, ...]  # primero las de ahorro, de la más barata a la más cara
    sin_cotizacion: tuple[str, ...]  # nombres de las opciones que la fuente no trajo
    reglas_al: str  # fecha en que se relevaron las normas impositivas

    @property
    def mas_barata(self) -> OpcionDeCompra:
        return next(o for o in self.opciones if o.para_ahorrar)


def _cargar_cotizaciones_actuales() -> dict[str, CotizacionActual]:
    try:
        return descargar_cotizaciones_actuales()
    except httpx.HTTPError as error:
        raise ErrorDeRed(
            f"No se pudieron descargar las cotizaciones del dólar ({error}). Probá de nuevo más tarde."
        ) from error
    except (KeyError, TypeError, ValueError, AttributeError) as error:
        raise ErrorSimulador(
            f"La API devolvió cotizaciones del dólar en un formato inesperado ({error!r})."
        ) from error


def comprar_dolares(pesos: float, comision_broker: float = 0.0) -> CompraDeDolares:
    """Cuántos dólares se consiguen con `pesos` en cada canal, con impuestos y cargos incluidos.

    `comision_broker` va en porcentaje (0,3 significa 0,3 %) y se suma solo en
    los canales que pasan por un broker (MEP y CCL).
    """
    if pesos <= 0:
        raise ErrorSimulador("El monto en pesos debe ser mayor que cero")
    if not 0 <= comision_broker < 100:
        raise ErrorSimulador("La comisión del broker debe estar entre 0 y 100 %")

    cotizaciones = _cargar_cotizaciones_actuales()
    hoy = _hoy()
    armadas = []
    sin_cotizacion = []
    for canal in CANALES:
        cotizacion = cotizaciones.get(canal.casa)
        if cotizacion is None:
            sin_cotizacion.append(canal.nombre)
            continue
        cargos = cargos_del_canal(canal, comision_broker / 100)
        try:
            efectivo = precio_efectivo(cotizacion.venta, cargos)
            dolares = dolares_obtenidos(pesos, efectivo)
        except ValueError as error:
            raise ErrorSimulador(f"{canal.nombre}: {error}") from error
        dia = cotizacion.actualizado.date()
        armadas.append((canal, cotizacion, cargos, efectivo, dolares, dia))

    ahorro = [a[3] for a in armadas if a[0].para_ahorrar]
    if not ahorro:
        raise ErrorSimulador("La fuente no trajo cotizaciones para ninguna forma de comprar dólares")
    minimo = min(ahorro)

    armadas.sort(key=lambda a: (not a[0].para_ahorrar, a[3]))
    opciones = tuple(
        OpcionDeCompra(
            clave=canal.clave,
            nombre=canal.nombre,
            precio=cotizacion.venta,
            actualizado=cotizacion.actualizado,
            fecha=dia.isoformat(),
            es_de_hoy=dia == hoy,
            cargos=cargos,
            precio_efectivo=efectivo,
            dolares=dolares,
            sobreprecio=efectivo / minimo - 1,
            notas=canal.notas,
            para_ahorrar=canal.para_ahorrar,
        )
        for canal, cotizacion, cargos, efectivo, dolares, dia in armadas
    )
    return CompraDeDolares(pesos, opciones, tuple(sin_cotizacion), REGLAS_RELEVADAS)


@dataclass(frozen=True)
class EscenarioCuotas:
    nombre: str  # a qué se compara el rendimiento de tu plata (plazo fijo, inflación)
    tasa_mensual: float
    valor_presente: float  # cuánto valen hoy las cuotas descontadas a esa tasa
    ahorro: float  # precio de contado menos valor presente: positivo si convienen las cuotas

    @property
    def mejor(self) -> str:
        if abs(self.ahorro) < 0.005:
            return "Da lo mismo"
        return "En cuotas" if self.ahorro > 0 else "De contado"


@dataclass(frozen=True)
class ComparacionCuotas:
    precio_lista: float  # precio pagando en cuotas
    cuotas: int
    valor_cuota: float
    descuento: float  # proporción: 0,10 es un 10 % de descuento por pagar de contado
    precio_contado: float
    tasa_equilibrio: float  # tasa mensual a la que da lo mismo una opción que la otra
    tna_equivalente: float
    plazo_fijo: EscenarioCuotas
    inflacion: EscenarioCuotas | None
    aviso: str | None = None

    @property
    def mejor(self) -> str:
        """Opción que conviene si tu plata queda en el plazo fijo."""
        return self.plazo_fijo.mejor


def comparar_contado_y_cuotas(
    precio: float,
    cuotas: int,
    tna: float,
    descuento: float = 0.0,
    inflacion_mensual: float | None = None,
) -> ComparacionCuotas:
    """¿Conviene pagar de contado o en cuotas sin interés?

    `precio` es el precio en cuotas (el de lista). `descuento` y `tna` van en
    porcentaje. Si no se indica `inflacion_mensual`, se usa la del último mes
    publicado por el INDEC; si no se puede obtener, se omite esa comparación.
    """
    if tna < 0:
        raise ErrorSimulador("La tasa no puede ser negativa")
    if inflacion_mensual is not None and inflacion_mensual <= -100:
        raise ErrorSimulador("La inflación mensual debe ser mayor que -100 %")
    try:
        contado = precio_de_contado(precio, descuento / 100)
        equilibrio = tasa_de_equilibrio(precio, cuotas, descuento / 100)
        tasa_pf = tasa_mensual_de_tna(tna / 100)
        plazo_fijo_ = _escenario_cuotas(f"Plazo fijo (TNA {pct(tna / 100)})", tasa_pf, precio, cuotas, contado)

        aviso = None
        inflacion = None
        if inflacion_mensual is not None:
            inflacion = _escenario_cuotas(
                f"Inflación ingresada ({pct(inflacion_mensual / 100)} por mes)",
                inflacion_mensual / 100,
                precio,
                cuotas,
                contado,
            )
        else:
            try:
                dato = consultar_inflacion_mes()
            except ErrorSimulador:
                aviso = "No se pudo obtener la inflación del INDEC, así que se omite esa comparación."
            else:
                aviso = dato.aviso
                inflacion = _escenario_cuotas(
                    f"Inflación de {nombre_mes(dato.mes)} ({pct(dato.variacion)} por mes)",
                    dato.variacion,
                    precio,
                    cuotas,
                    contado,
                )
    except ValueError as error:
        raise ErrorSimulador(str(error)) from error

    return ComparacionCuotas(
        precio_lista=precio,
        cuotas=int(cuotas),
        valor_cuota=precio / cuotas,
        descuento=descuento / 100,
        precio_contado=contado,
        tasa_equilibrio=equilibrio,
        tna_equivalente=tna_de_tasa_mensual(equilibrio),
        plazo_fijo=plazo_fijo_,
        inflacion=inflacion,
        aviso=aviso,
    )


def _escenario_cuotas(
    nombre: str, tasa_mensual: float, precio: float, cuotas: int, contado: float
) -> EscenarioCuotas:
    valor_presente = valor_presente_de_cuotas(precio, cuotas, tasa_mensual)
    return EscenarioCuotas(nombre, tasa_mensual, valor_presente, contado - valor_presente)
