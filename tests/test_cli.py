from datetime import datetime

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
from typer.testing import CliRunner

from simulador import cli, servicio

runner = CliRunner()


def _parchear(monkeypatch, ipc=IPC_7_MESES, blue=None, hoy=(2026, 10, 13), en_vivo=None):
    from datetime import date

    monkeypatch.setattr(servicio, "_hoy", lambda: date(*hoy))
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: ipc)
    monkeypatch.setattr(
        servicio, "descargar_blue", lambda usar_cache=True: blue if blue is not None else cotizaciones_blue()
    )
    monkeypatch.setattr(servicio, "descargar_blue_actual", lambda: en_vivo or blue_actual())
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales())


def _invocar(*args):
    return runner.invoke(cli.app, list(args))


# --- inflación ---------------------------------------------------------------

def test_inflacion_muestra_meses_y_acumulada(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("inflacion", "--meses", "3")
    assert r.exit_code == 0
    assert "2026-07" in r.output
    assert "3,00 %" in r.output
    assert "Acumulada en 3 meses: 9,27 %" in r.output


def test_inflacion_mes_sin_opciones_muestra_el_mes_pasado_con_aviso(monkeypatch):
    _parchear(monkeypatch, ipc=IPC_20_MESES)
    r = _invocar("inflacion-mes")
    assert r.exit_code == 0
    assert "todavía no publicó la inflación de septiembre de 2026" in r.output
    assert "Inflación de agosto de 2026: 2,00 %" in r.output
    assert "Interanual: 26,82 %" in r.output


def test_inflacion_mes_puntual(monkeypatch):
    _parchear(monkeypatch, ipc=IPC_20_MESES)
    r = _invocar("inflacion-mes", "--anio", "2025", "--mes", "3")
    assert r.exit_code == 0
    assert "Inflación de marzo de 2025: 2,00 %" in r.output
    assert "Interanual" not in r.output  # no hay dato de marzo de 2024


def test_inflacion_mes_con_solo_el_anio_falla(monkeypatch):
    _parchear(monkeypatch, ipc=IPC_20_MESES)
    r = _invocar("inflacion-mes", "--anio", "2025")
    assert r.exit_code == 1
    assert "año y el mes juntos" in r.output


# --- dólar -------------------------------------------------------------------

def test_dolar_muestra_el_valor_y_cuando_se_actualizo(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("dolar")
    assert r.exit_code == 0
    assert "Dólar blue: compra $ 1.520,00 | venta $ 1.540,00 (actualizado hoy a las 14:30)" in r.output
    assert "puede no reflejar" not in r.output
    assert "Comprar un dólar cuesta $ 1.540,00; venderlo paga $ 1.520,00." in r.output


def test_dolar_avisa_si_el_dato_no_se_actualizo_hoy(monkeypatch):
    ayer = blue_actual(actualizado=datetime(2026, 10, 12, 17, 56, tzinfo=ZONA_AR))
    _parchear(monkeypatch, en_vivo=ayer)
    r = _invocar("dolar")
    assert "(actualizado el 12/10 a las 17:56)" in r.output
    assert "puede no reflejar la cotización de este momento" in r.output


def test_dolar_usa_el_historial_si_falla_la_fuente_en_vivo(monkeypatch):
    _parchear(monkeypatch)

    def falla():
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(servicio, "descargar_blue_actual", falla)
    r = _invocar("dolar")
    assert r.exit_code == 0
    assert (
        "compra $ 1.590,00 | venta $ 1.610,00 (último cierre diario del 2026-07-28, sin hora informada)"
        in r.output
    )
    assert "puede no reflejar" in r.output


# --- plazo fijo --------------------------------------------------------------

def test_plazo_fijo_usa_ipc_real_si_no_se_pasa_inflacion(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("plazo-fijo", "--capital", "1000000", "--tna", "35", "--meses", "6")
    assert r.exit_code == 0
    assert "Inflación real (INDEC, IPC nacional): 2026-02 a 2026-07" in r.output
    assert "Inflación acumulada:    19,41 %" in r.output


def test_plazo_fijo_con_inflacion_manual_no_descarga(monkeypatch):
    def no_deberia_llamarse(*args, **kwargs):
        raise AssertionError("no debería descargar nada")

    monkeypatch.setattr(servicio, "descargar_serie", no_deberia_llamarse)
    r = _invocar(
        "plazo-fijo", "--capital", "1000000", "--tna", "35", "--meses", "6",
        "--inflacion-mensual", "3.5",
    )
    assert r.exit_code == 0
    assert "Inflación acumulada:    22,93 %" in r.output


def test_plazo_fijo_error_de_red_sugiere_inflacion_manual(monkeypatch):
    def falla(*args, **kwargs):
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(servicio, "descargar_serie", falla)
    r = _invocar("plazo-fijo", "--capital", "1000", "--tna", "35")
    assert r.exit_code == 1
    assert "No se pudo descargar el IPC" in r.output
    assert "--inflacion-mensual" in r.output


def test_plazo_fijo_parametros_invalidos(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("plazo-fijo", "--capital", "0", "--tna", "35")
    assert r.exit_code == 1
    assert "capital" in r.output


# --- comparar ----------------------------------------------------------------

def test_comparar_muestra_estrategias_mejor_y_blue_de_hoy(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("comparar", "--capital", "1000000", "--tna", "35", "--meses", "6")
    assert r.exit_code == 0
    assert "Período: 2026-01 a 2026-07 (6 meses)" in r.output
    assert "comprás a $ 1.010,00 (fin de 2026-01)" in r.output
    assert "vendés a $ 1.590,00 (fin de 2026-07)" in r.output
    assert "Plazo fijo" in r.output and "Dólar blue" in r.output
    assert "Inflación acumulada: 19,41 %" in r.output
    assert "Mejor en términos reales: Dólar blue" in r.output
    assert "Dólar blue: compra $ 1.520,00 | venta $ 1.540,00 (actualizado hoy a las 14:30)" in r.output


def test_comparar_falla_claro_si_falta_un_mes_del_blue(monkeypatch):
    _parchear(monkeypatch, blue=cotizaciones_blue(range(2, 8)))
    r = _invocar("comparar", "--capital", "1000", "--tna", "35")
    assert r.exit_code == 1
    assert "2026-01" in r.output


@pytest.mark.parametrize(
    "error, texto",
    [
        (httpx.ConnectError("sin conexión"), "No se pudo descargar el dólar blue"),
        (KeyError("fecha"), "formato inesperado"),
    ],
)
def test_comparar_errores_del_blue(monkeypatch, error, texto):
    _parchear(monkeypatch)

    def falla(*args, **kwargs):
        raise error

    monkeypatch.setattr(servicio, "descargar_blue", falla)
    r = _invocar("comparar", "--capital", "1000", "--tna", "35")
    assert r.exit_code == 1
    assert texto in r.output


# --- comprar dólares ---------------------------------------------------------

def test_comprar_dolares_muestra_el_resumen_la_tabla_y_los_impuestos(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("comprar-dolares", "--pesos", "1000000")
    assert r.exit_code == 0
    assert "la opción más barata es Dólar oficial (banco): conseguís USD 651,47" in r.output
    assert "Dólar tarjeta (exterior)" in r.output
    assert "+30,00 % (solo para pagar)" in r.output
    assert "Se suma: Percepción 30 %" in r.output
    assert "Sin impuestos ni cargos incluidos en el precio." in r.output
    assert "relevados al 13/10/2026" in r.output


def test_comprar_dolares_aplica_la_comision_del_broker(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("comprar-dolares", "--pesos", "1000000", "--comision-broker", "0.5")
    assert r.exit_code == 0
    assert "Se suma: Comisión del broker, 0,50 %." in r.output


def test_comprar_dolares_monto_invalido(monkeypatch):
    _parchear(monkeypatch)
    r = _invocar("comprar-dolares", "--pesos", "0")
    assert r.exit_code == 1
    assert "mayor que cero" in r.output


def test_comprar_dolares_sin_red(monkeypatch):
    _parchear(monkeypatch)

    def falla():
        raise httpx.ConnectError("sin conexión")

    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", falla)
    r = _invocar("comprar-dolares", "--pesos", "1000000")
    assert r.exit_code == 1
    assert "No se pudieron descargar las cotizaciones del dólar" in r.output
