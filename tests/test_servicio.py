from datetime import date, datetime

import httpx
import pytest
from datos_de_prueba import (
    IPC_7_MESES,
    IPC_20_MESES,
    ZONA_AR,
    blue_actual,
    cotizaciones_actuales,
    cotizaciones_blue,
)

from simulador import servicio
from simulador.servicio import ErrorDeRed, ErrorSimulador

HOY = date(2026, 10, 13)


@pytest.fixture(autouse=True)
def datos_por_defecto(monkeypatch):
    monkeypatch.setattr(servicio, "_hoy", lambda: HOY)
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: IPC_20_MESES)
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: cotizaciones_blue())
    monkeypatch.setattr(servicio, "descargar_blue_actual", lambda: blue_actual())
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales())


def _con_ipc_de_7_meses(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: IPC_7_MESES)


# --- inflación ---------------------------------------------------------------

def test_inflacion_ultimos_meses_devuelve_fechas_y_variaciones():
    datos = servicio.inflacion_ultimos_meses(3)
    assert [fecha for fecha, _ in datos] == ["2026-06-01", "2026-07-01", "2026-08-01"]
    assert [v for _, v in datos] == pytest.approx([0.02] * 3)


def test_inflacion_ultimos_meses_sin_datos_suficientes():
    with pytest.raises(ErrorSimulador):
        servicio.inflacion_ultimos_meses(100)


def test_mes_pasado_sin_publicar_muestra_el_ultimo_disponible_con_aviso():
    r = servicio.consultar_inflacion_mes()  # hoy es 2026-10-13, falta septiembre
    assert r.mes == "2026-08"
    assert r.variacion == pytest.approx(0.02)
    assert "todavía no publicó" in r.aviso
    assert "septiembre de 2026" in r.aviso


def test_mes_pasado_publicado_no_lleva_aviso(monkeypatch):
    monkeypatch.setattr(servicio, "_hoy", lambda: date(2026, 9, 20))
    r = servicio.consultar_inflacion_mes()
    assert r.mes == "2026-08"
    assert r.aviso is None


def test_mes_puntual_con_interanual():
    r = servicio.consultar_inflacion_mes(2026, 3)
    assert r.mes == "2026-03"
    assert r.variacion == pytest.approx(0.02)
    assert r.interanual == pytest.approx(1.02**12 - 1)


def test_mes_puntual_sin_dato_del_anio_anterior_no_tiene_interanual():
    r = servicio.consultar_inflacion_mes(2025, 3)
    assert r.interanual is None


def test_mes_futuro_dice_cual_es_el_ultimo_publicado():
    with pytest.raises(ErrorSimulador, match="todavía no publicó") as error:
        servicio.consultar_inflacion_mes(2026, 12)
    assert "agosto de 2026" in str(error.value)


def test_primer_mes_de_la_serie_no_tiene_variacion():
    with pytest.raises(ErrorSimulador, match="No hay datos de inflación para enero de 2025"):
        servicio.consultar_inflacion_mes(2025, 1)


def test_anio_sin_mes_falla():
    with pytest.raises(ErrorSimulador, match="año y el mes juntos"):
        servicio.consultar_inflacion_mes(anio=2025)


def test_mes_fuera_de_rango_falla():
    with pytest.raises(ErrorSimulador, match="entre 1 y 12"):
        servicio.consultar_inflacion_mes(2025, 13)


# --- dólar de hoy ------------------------------------------------------------

def test_dolar_hoy_usa_la_cotizacion_en_vivo_y_marca_que_se_actualizo_hoy():
    d = servicio.dolar_hoy()
    assert (d.compra, d.venta) == (1520.0, 1540.0)
    assert d.fecha == "2026-10-13"
    assert d.actualizado.hour == 14
    assert d.es_de_hoy is True


def test_dolar_hoy_marca_como_viejo_un_dato_actualizado_ayer(monkeypatch):
    ayer = datetime(2026, 10, 12, 17, 56, tzinfo=ZONA_AR)
    monkeypatch.setattr(servicio, "descargar_blue_actual", lambda: blue_actual(actualizado=ayer))
    d = servicio.dolar_hoy()
    assert d.fecha == "2026-10-12"
    assert d.es_de_hoy is False


def test_dolar_hoy_usa_el_historial_si_falla_la_fuente_en_vivo(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_blue_actual", _falla_con(httpx.ConnectError("sin conexión")))
    d = servicio.dolar_hoy()
    assert (d.fecha, d.compra, d.venta) == ("2026-07-28", 1590.0, 1610.0)
    assert d.actualizado is None
    assert d.es_de_hoy is False  # el historial no informa la hora, nunca se da por de hoy


def test_dolar_hoy_usa_el_historial_si_la_fuente_en_vivo_viene_mal(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_blue_actual", _falla_con(KeyError("fechaActualizacion")))
    assert servicio.dolar_hoy().fecha == "2026-07-28"


def test_dolar_hoy_sin_ninguna_fuente_falla(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_blue_actual", _falla_con(httpx.ConnectError("sin conexión")))
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: [])
    with pytest.raises(ErrorSimulador):
        servicio.dolar_hoy()


# --- plazo fijo --------------------------------------------------------------

def test_plazo_fijo_con_ipc_real(monkeypatch):
    _con_ipc_de_7_meses(monkeypatch)
    sim = servicio.calcular_plazo_fijo(1_000_000, 35, 6)
    assert (sim.desde, sim.hasta) == ("2026-02", "2026-07")
    assert sim.resultado.inflacion_acumulada == pytest.approx(1.03**6 - 1)


def test_plazo_fijo_con_inflacion_manual_no_descarga(monkeypatch):
    def no_deberia_llamarse(*args, **kwargs):
        raise AssertionError("no debería descargar nada")

    monkeypatch.setattr(servicio, "descargar_serie", no_deberia_llamarse)
    sim = servicio.calcular_plazo_fijo(1_000_000, 35, 6, inflacion_mensual=3.5)
    assert sim.desde is None and sim.hasta is None
    assert sim.resultado.inflacion_acumulada == pytest.approx(1.035**6 - 1)


@pytest.mark.parametrize(
    "capital, tna, meses, mensaje",
    [(0, 35, 6, "capital"), (1000, -1, 6, "tasa"), (1000, 35, 0, "meses")],
)
def test_validaciones_de_parametros(capital, tna, meses, mensaje):
    with pytest.raises(ErrorSimulador, match=mensaje):
        servicio.calcular_plazo_fijo(capital, tna, meses, inflacion_mensual=3)
    with pytest.raises(ErrorSimulador, match=mensaje):
        servicio.comparar_estrategias(capital, tna, meses)


# --- comparación ------------------------------------------------------------

def test_comparar_compra_a_venta_y_vende_a_compra_en_cierres_de_mes(monkeypatch):
    _con_ipc_de_7_meses(monkeypatch)
    c = servicio.comparar_estrategias(1_000_000, 35, 6)
    assert (c.inicio, c.fin) == ("2026-01", "2026-07")
    assert c.precio_compra == 1010.0  # venta de enero: lo que pagás
    assert c.precio_venta == 1590.0  # compra de julio: lo que recibís
    assert c.mejor == "Dólar blue"
    assert c.blue_hoy.fecha == "2026-10-13"
    assert c.blue_hoy.es_de_hoy is True


def test_comparar_gana_el_plazo_fijo_si_el_dolar_pierde(monkeypatch):
    _con_ipc_de_7_meses(monkeypatch)
    quieto = [(f"2026-{m:02d}-28", 1000.0, 1020.0) for m in range(1, 8)]
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: quieto)
    assert servicio.comparar_estrategias(1_000_000, 35, 6).mejor == "Plazo fijo"


def test_comparar_falla_si_falta_un_mes_del_blue(monkeypatch):
    _con_ipc_de_7_meses(monkeypatch)
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: cotizaciones_blue(range(2, 8)))
    with pytest.raises(ErrorSimulador, match="2026-01"):
        servicio.comparar_estrategias(1_000, 35, 6)


# --- errores de red y de formato ---------------------------------------------

def _falla_con(error):
    def descargar(*args, **kwargs):
        raise error

    return descargar


def test_error_de_red_del_ipc(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_serie", _falla_con(httpx.ConnectError("sin conexión")))
    with pytest.raises(ErrorDeRed, match="IPC"):
        servicio.inflacion_ultimos_meses(6)


def test_error_de_red_del_blue(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_blue_actual", _falla_con(httpx.ConnectError("sin conexión")))
    monkeypatch.setattr(servicio, "descargar_blue", _falla_con(httpx.ConnectError("sin conexión")))
    with pytest.raises(ErrorDeRed, match="dólar blue"):
        servicio.dolar_hoy()


def test_formato_inesperado_no_es_error_de_red(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_blue_actual", _falla_con(KeyError("fechaActualizacion")))
    monkeypatch.setattr(servicio, "descargar_blue", _falla_con(KeyError("fecha")))
    with pytest.raises(ErrorSimulador, match="formato inesperado") as error:
        servicio.dolar_hoy()
    assert not isinstance(error.value, ErrorDeRed)


# --- comprar dólares ---------------------------------------------------------

def _opcion(compra, clave):
    return next(o for o in compra.opciones if o.clave == clave)


def test_comprar_dolares_ordena_de_la_mas_barata_a_la_mas_cara_y_deja_la_tarjeta_al_final():
    c = servicio.comprar_dolares(1_000_000)
    assert [o.clave for o in c.opciones] == ["oficial", "blue", "mep", "ccl", "cripto", "tarjeta"]
    assert c.mas_barata.clave == "oficial"
    assert c.reglas_al == "13/10/2026"


def test_comprar_dolares_calcula_dolares_y_sobreprecio():
    c = servicio.comprar_dolares(1_000_000)
    oficial, blue = _opcion(c, "oficial"), _opcion(c, "blue")
    assert oficial.precio_efectivo == pytest.approx(1535)
    assert oficial.dolares == pytest.approx(1_000_000 / 1535)
    assert oficial.sobreprecio == 0
    assert blue.sobreprecio == pytest.approx(1540 / 1535 - 1)


def test_el_dolar_tarjeta_suma_el_30_por_ciento_y_no_cuenta_para_ahorrar():
    c = servicio.comprar_dolares(1_000_000)
    tarjeta = _opcion(c, "tarjeta")
    assert tarjeta.precio == 1535
    assert tarjeta.precio_efectivo == pytest.approx(1535 * 1.30)
    assert tarjeta.para_ahorrar is False
    assert tarjeta.sobreprecio == pytest.approx(0.30)
    assert [o.clave for o in c.opciones if o.para_ahorrar] == ["oficial", "blue", "mep", "ccl", "cripto"]


def test_la_comision_del_broker_encarece_solo_mep_y_ccl():
    base = servicio.comprar_dolares(1_000_000)
    con_comision = servicio.comprar_dolares(1_000_000, comision_broker=0.5)
    assert _opcion(con_comision, "mep").precio_efectivo == pytest.approx(1542.9 * 1.005)
    assert _opcion(con_comision, "ccl").precio_efectivo == pytest.approx(1606.6 * 1.005)
    assert _opcion(con_comision, "blue").precio_efectivo == _opcion(base, "blue").precio_efectivo
    assert _opcion(con_comision, "oficial").precio_efectivo == _opcion(base, "oficial").precio_efectivo


def test_cada_opcion_dice_cuando_se_actualizo_su_cotizacion():
    c = servicio.comprar_dolares(1_000_000)
    oficial, blue = _opcion(c, "oficial"), _opcion(c, "blue")
    assert (oficial.fecha, oficial.es_de_hoy) == ("2026-10-09", False)
    assert (blue.fecha, blue.es_de_hoy) == ("2026-10-13", True)


def test_si_la_fuente_no_trae_una_opcion_se_informa_y_se_sigue(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales(sin=("cripto",)))
    c = servicio.comprar_dolares(1_000_000)
    assert "cripto" not in [o.clave for o in c.opciones]
    assert c.sin_cotizacion == ("Dólar cripto (USDT)",)


def test_sin_ninguna_cotizacion_falla(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: {})
    with pytest.raises(ErrorSimulador, match="ninguna forma"):
        servicio.comprar_dolares(1_000_000)


@pytest.mark.parametrize("pesos, comision", [(0, 0), (-1, 0), (1000, -1), (1000, 100)])
def test_comprar_dolares_valida_los_parametros(pesos, comision):
    with pytest.raises(ErrorSimulador):
        servicio.comprar_dolares(pesos, comision)


def test_comprar_dolares_sin_red_da_error_de_red(monkeypatch):
    def falla():
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", falla)
    with pytest.raises(ErrorDeRed, match="cotizaciones del dólar"):
        servicio.comprar_dolares(1_000_000)


def test_comprar_dolares_con_formato_inesperado(monkeypatch):
    def mal():
        raise KeyError("casa")

    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", mal)
    with pytest.raises(ErrorSimulador, match="formato inesperado"):
        servicio.comprar_dolares(1_000_000)


# --- contado o cuotas --------------------------------------------------------

def _valor_presente_a_mano(cuota, n, m):
    """Anualidad vencida: cuota * (1 - (1 + m) ** -n) / m, calculada aparte del código."""
    return cuota * (1 - (1 + m) ** -n) / m


def test_cuotas_con_descuento_grande_conviene_el_contado():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    m = 0.35 * 30 / 365
    esperado = _valor_presente_a_mano(20_000, 6, m)
    assert c.precio_contado == pytest.approx(108_000)
    assert c.valor_cuota == pytest.approx(20_000)
    assert c.plazo_fijo.valor_presente == pytest.approx(esperado)
    assert c.plazo_fijo.ahorro == pytest.approx(108_000 - esperado)
    # Contrastado con un cálculo aparte: las cuotas valen hoy $ 108.787,95 y el contado ahorra $ 787,95.
    assert c.plazo_fijo.valor_presente == pytest.approx(108_787.95, abs=0.01)
    assert c.plazo_fijo.ahorro == pytest.approx(-787.95, abs=0.01)
    assert c.mejor == "De contado"
    assert c.descuento == pytest.approx(0.10)


def test_cuotas_la_tasa_de_equilibrio_es_el_credito_implicito():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    assert c.tasa_equilibrio == pytest.approx(0.03096, abs=1e-5)  # 3,10 % por mes
    assert c.tna_equivalente * 100 == pytest.approx(37.668, abs=0.01)  # apenas arriba del 35 % del plazo fijo


def test_cuotas_conviene_si_el_plazo_fijo_rinde_mas_que_el_equilibrio():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=45, descuento=10)
    assert c.mejor == "En cuotas"
    assert c.plazo_fijo.ahorro > 0


def test_cuotas_sin_descuento_las_cuotas_siempre_convienen():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35)
    assert c.precio_contado == 120_000
    assert c.tasa_equilibrio == 0
    assert c.mejor == "En cuotas"
    assert c.plazo_fijo.ahorro == pytest.approx(120_000 - _valor_presente_a_mano(20_000, 6, 0.35 * 30 / 365))


def test_cuotas_con_tna_cero_y_descuento_conviene_el_contado():
    c = servicio.comparar_contado_y_cuotas(100_000, 3, tna=0, descuento=5)
    assert c.plazo_fijo.valor_presente == pytest.approx(100_000)
    assert c.plazo_fijo.ahorro == pytest.approx(-5_000)
    assert c.mejor == "De contado"


def test_cuotas_una_sola_cuota_con_tasa_exacta_da_lo_mismo():
    # 1000 en un mes o 900 hoy equivale a 11,11 % mensual; un plazo fijo con esa tasa mensual empata.
    tna = (1000 / 900 - 1) * 365 / 30 * 100
    c = servicio.comparar_contado_y_cuotas(1000, 1, tna=tna, descuento=10)
    assert c.mejor == "Da lo mismo"


def test_cuotas_usa_la_inflacion_del_ultimo_mes_del_indec_por_defecto():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)  # hoy 13/10/2026: último dato, agosto
    assert c.inflacion.nombre == "Inflación de agosto de 2026 (2,00 % por mes)"
    assert c.inflacion.tasa_mensual == pytest.approx(0.02)
    assert c.inflacion.valor_presente == pytest.approx(_valor_presente_a_mano(20_000, 6, 0.02))
    assert "todavía no publicó" in c.aviso  # septiembre aún no salió


def test_cuotas_con_inflacion_ingresada_no_consulta_al_indec(monkeypatch):
    def no_deberia_llamarse(*a, **k):
        raise AssertionError("no debería descargar el IPC")

    monkeypatch.setattr(servicio, "descargar_serie", no_deberia_llamarse)
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10, inflacion_mensual=3)
    assert c.inflacion.nombre == "Inflación ingresada (3,00 % por mes)"
    assert c.inflacion.valor_presente == pytest.approx(_valor_presente_a_mano(20_000, 6, 0.03))
    assert c.aviso is None


def test_cuotas_sin_acceso_al_indec_omite_la_inflacion_y_sigue(monkeypatch):
    def falla(serie_id, usar_cache=True):
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(servicio, "descargar_serie", falla)
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    assert c.inflacion is None
    assert "se omite" in c.aviso
    assert c.mejor == "De contado"


@pytest.mark.parametrize(
    "precio, cuotas, tna, descuento, inflacion",
    [
        (0, 6, 35, 0, None),
        (-1, 6, 35, 0, None),
        (1000, 0, 35, 0, None),
        (1000, 6, -1, 0, None),
        (1000, 6, 35, -5, None),
        (1000, 6, 35, 100, None),
        (1000, 6, 35, 0, -100),
    ],
)
def test_cuotas_valida_los_parametros(precio, cuotas, tna, descuento, inflacion):
    with pytest.raises(ErrorSimulador):
        servicio.comparar_contado_y_cuotas(precio, cuotas, tna, descuento, inflacion)
