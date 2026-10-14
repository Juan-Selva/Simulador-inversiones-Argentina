from datetime import date, datetime

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
from simulador.interfaz import vistas
from simulador.interfaz.vistas import Celda, tono_de
from simulador.servicio import DolarHoy


@pytest.fixture(autouse=True)
def datos(monkeypatch):
    monkeypatch.setattr(servicio, "_hoy", lambda: date(2026, 10, 13))
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: IPC_7_MESES)
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: cotizaciones_blue())
    monkeypatch.setattr(servicio, "descargar_blue_actual", lambda: blue_actual())
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales())


def test_tono_de_usa_el_valor_tal_como_se_muestra():
    assert tono_de(0.05) == "positivo"
    assert tono_de(-0.05) == "negativo"
    assert tono_de(0) == "normal"
    assert tono_de(-0.000001) == "normal"  # se muestra como -0,00 %


def test_tarjeta_blue_muestra_cuando_se_actualizo_y_avisa_si_no_es_de_hoy():
    de_hoy = DolarHoy(1500.0, 1520.0, datetime(2026, 10, 13, 14, 30, tzinfo=ZONA_AR), "2026-10-13", True)
    de_ayer = DolarHoy(1500.0, 1520.0, datetime(2026, 10, 12, 17, 56, tzinfo=ZONA_AR), "2026-10-12", False)
    sin_hora = DolarHoy(1500.0, 1520.0, None, "2026-10-09", False)

    assert vistas.tarjeta_blue(de_hoy) == (
        "Compra $ 1.500,00  |  Venta $ 1.520,00",
        "Actualizado hoy a las 14:30",
    )
    assert vistas.tarjeta_blue(de_ayer)[1] == "Actualizado el 12/10 a las 17:56"
    assert vistas.tarjeta_blue(sin_hora)[1] == "Último cierre diario del 2026-10-09, sin hora informada"

    assert vistas.aviso_blue(de_hoy) is None
    assert "puede no reflejar" in vistas.aviso_blue(de_ayer)
    assert "puede no reflejar" in vistas.aviso_blue(sin_hora)


def test_filas_plazo_fijo_marcan_en_rojo_el_rendimiento_real_negativo():
    sim = servicio.calcular_plazo_fijo(1_000_000, 35, 6)
    filas = dict(vistas.filas_plazo_fijo(sim))
    assert filas["Capital inicial"] == Celda("$ 1.000.000,00")
    assert filas["Inflación acumulada"].texto == "19,41 %"
    assert filas["Rendimiento real"] == Celda("-0,72 %", "negativo")
    assert filas["Rendimiento nominal"].tono == "positivo"


def test_periodo_plazo_fijo_real_y_manual():
    real = servicio.calcular_plazo_fijo(1_000_000, 35, 6)
    manual = servicio.calcular_plazo_fijo(1_000_000, 35, 6, inflacion_mensual=3)
    assert vistas.periodo_plazo_fijo(real) == "Inflación real del INDEC: febrero de 2026 a julio de 2026"
    assert "constante" in vistas.periodo_plazo_fijo(manual)


def test_comparacion_tabla_resumen_y_veredicto():
    c = servicio.comparar_estrategias(1_000_000, 35, 6)
    filas = vistas.filas_comparacion(c)
    assert [fila[0].texto for fila in filas] == ["Plazo fijo", "Dólar blue"]
    assert filas[0][2].tono == "negativo"  # el plazo fijo no le gana a la inflación
    assert filas[1][2].tono == "positivo"  # el dólar sí
    assert all(len(fila) == len(vistas.CABECERA_COMPARACION) for fila in filas)

    resumen = vistas.resumen_comparacion(c)
    assert "enero de 2026 a julio de 2026 (6 meses)" in resumen[0]
    assert "$ 1.010,00" in resumen[1] and "$ 1.590,00" in resumen[1]
    assert resumen[2] == "Inflación acumulada del período: 19,41 %"
    assert vistas.veredicto(c) == "Mejor en términos reales: Dólar blue"


def test_filas_inflacion_mes_con_y_sin_interanual(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: IPC_20_MESES)
    con = vistas.filas_inflacion_mes(servicio.consultar_inflacion_mes(2026, 3))
    sin = vistas.filas_inflacion_mes(servicio.consultar_inflacion_mes(2025, 3))
    assert con == [
        ("Inflación de marzo de 2026", Celda("2,00 %")),
        ("Interanual", Celda("26,82 %")),
    ]
    assert len(sin) == 1


def test_filas_inflacion_meses_agrega_la_acumulada_al_final():
    datos = servicio.inflacion_ultimos_meses(3)
    filas = vistas.filas_inflacion_meses(datos)
    assert [fila[0].texto for fila in filas] == [
        "Mayo de 2026", "Junio de 2026", "Julio de 2026", "Acumulada en 3 meses",
    ]
    assert filas[0][1].texto == "3,00 %"
    assert filas[-1][1].texto == "9,27 %"


# --- comprar dólares ---------------------------------------------------------

def test_resumen_compra_nombra_la_opcion_mas_barata():
    texto = vistas.resumen_compra(servicio.comprar_dolares(1_000_000))
    assert "$ 1.000.000,00" in texto
    assert "Dólar oficial (banco)" in texto
    assert "USD 651,47" in texto


def test_filas_compra_marcan_la_mas_barata_los_cargos_y_el_sobreprecio():
    filas = vistas.filas_compra(servicio.comprar_dolares(1_000_000))
    assert all(len(fila) == len(vistas.CABECERA_COMPRA) for fila in filas)
    oficial, blue = filas[0], filas[1]
    assert oficial[0].texto == "Dólar oficial (banco)"
    assert oficial[1].texto == "Ninguno"
    assert oficial[2].texto == "$ 1.535,00"
    assert oficial[4] == Celda("La más barata", "positivo")
    assert blue[4] == Celda("+0,33 %", "negativo")


def test_filas_compra_aclara_que_la_tarjeta_es_solo_para_pagar():
    tarjeta = vistas.filas_compra(servicio.comprar_dolares(1_000_000))[-1]
    assert tarjeta[0].texto == "Dólar tarjeta (exterior)"
    assert tarjeta[1].texto == "30,00 %"
    assert tarjeta[2].texto == "$ 1.995,50"
    assert tarjeta[4].texto == "+30,00 % (solo para pagar)"


def test_detalle_compra_incluye_cotizacion_cargos_y_condiciones():
    c = servicio.comprar_dolares(1_000_000)
    oficial = vistas.detalle_compra(c.opciones[0])
    assert oficial[0] == "Cotización de venta $ 1.535,00, actualizado el 09/10 a las 15:55."
    assert oficial[1] == "Sin impuestos ni cargos incluidos en el precio."
    assert any("90 días" in linea for linea in oficial)

    tarjeta = vistas.detalle_compra(c.opciones[-1])
    assert any(linea.startswith("Se suma: Percepción 30 %") and linea.endswith("30,00 %.") for linea in tarjeta)


def test_pie_compra_avisa_de_la_fuente_las_normas_y_lo_que_falte(monkeypatch):
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales(sin=("cripto",)))
    pie = vistas.pie_compra(servicio.comprar_dolares(1_000_000))
    assert any("DolarAPI" in linea for linea in pie)
    assert any("relevados al 13/10/2026" in linea for linea in pie)
    assert pie[-1] == "Sin cotización de la fuente para: Dólar cripto (USDT)."


# --- tema --------------------------------------------------------------------

def test_temas_y_etiquetas_de_tema():
    assert vistas.TEMAS == {"☀": "light", "☾": "dark"}
    assert vistas.etiqueta_de_tema("dark") == "☾"
    assert vistas.etiqueta_de_tema("light") == "☀"
    assert vistas.etiqueta_de_tema("violeta") == "☀"
    assert all(vistas.etiqueta_de_tema(modo) == etiqueta for etiqueta, modo in vistas.TEMAS.items())


# --- contado o cuotas --------------------------------------------------------

def test_filas_cuotas_con_descuento_muestran_el_credito_implicito():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    filas = dict(vistas.filas_cuotas(c))
    assert filas["Precio en cuotas"].texto == "$ 120.000,00"
    assert filas["Cuotas"].texto == "6 de $ 20.000,00"
    assert filas["Precio de contado"].texto == "$ 108.000,00 (10,00 % de descuento)"
    assert filas["Pagar en cuotas equivale a un crédito al"].texto == "3,10 % por mes (TNA 37,67 %)"


def test_filas_cuotas_sin_descuento_no_muestra_el_credito_implicito():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35)
    filas = dict(vistas.filas_cuotas(c))
    assert filas["Precio de contado"].texto == "$ 120.000,00 (sin descuento)"
    assert "Pagar en cuotas equivale a un crédito al" not in filas


def test_escenarios_cuotas_dicen_que_conviene_en_cada_caso():
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    plazo_fijo, inflacion = vistas.filas_escenarios_cuotas(c)
    assert plazo_fijo[0].texto == "Plazo fijo (TNA 35,00 %)"
    assert plazo_fijo[2].texto == "De contado (ahorrás $ 787,95)"
    assert inflacion[0].texto == "Inflación de julio de 2026 (3,00 % por mes)"  # esta batería usa el IPC de 7 meses
    assert inflacion[2].texto.startswith("De contado")


def test_escenarios_cuotas_sin_inflacion_solo_trae_el_plazo_fijo(monkeypatch):
    c = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10, inflacion_mensual=None)
    c = servicio.ComparacionCuotas(**{**c.__dict__, "inflacion": None})
    assert len(vistas.filas_escenarios_cuotas(c)) == 1


def test_veredicto_cuotas_en_los_tres_casos():
    contado = servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10)
    cuotas = servicio.comparar_contado_y_cuotas(120_000, 6, tna=45, descuento=10)
    empate = servicio.comparar_contado_y_cuotas(1000, 1, tna=(1000 / 900 - 1) * 365 / 30 * 100, descuento=10)
    assert vistas.veredicto_cuotas(contado).startswith("Conviene pagar de contado: ahorrás $ 787,95")
    assert vistas.veredicto_cuotas(cuotas).startswith("Conviene pagar en cuotas")
    assert vistas.veredicto_cuotas(empate).startswith("Da lo mismo")


def test_notas_cuotas_avisan_cuando_no_hay_descuento_y_del_aviso_del_indec():
    sin = vistas.notas_cuotas(servicio.comparar_contado_y_cuotas(120_000, 6, tna=35))
    con = vistas.notas_cuotas(servicio.comparar_contado_y_cuotas(120_000, 6, tna=35, descuento=10))
    assert any("siempre convienen" in nota for nota in sin)
    assert not any("siempre convienen" in nota for nota in con)
    assert any("primera cuota se paga a los 30 días" in nota for nota in con)
    assert any("todavía no publicó" in nota for nota in con)
