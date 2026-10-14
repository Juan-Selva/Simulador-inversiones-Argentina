from datetime import timedelta

import pytest

from simulador.ingesta import dolar
from simulador.ingesta.dolar import cierres_mensuales

COTIZACIONES = [
    ("2026-02-27", 1405.0, 1425.0),
    ("2026-01-05", 1300.0, 1320.0),
    ("2026-01-30", 1350.0, 1370.0),
    ("2026-02-02", 1360.0, 1380.0),
]  # desordenadas a propósito


def test_cierres_mensuales_toma_el_ultimo_dia_de_cada_mes():
    assert cierres_mensuales(COTIZACIONES, "venta") == [("2026-01", 1370.0), ("2026-02", 1425.0)]
    assert cierres_mensuales(COTIZACIONES, "compra") == [("2026-01", 1350.0), ("2026-02", 1405.0)]


def test_cierres_mensuales_rechaza_campo_invalido():
    with pytest.raises(ValueError):
        cierres_mensuales(COTIZACIONES, "promedio")


class _Respuesta:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


def test_descargar_blue_ordena_filtra_vacios_y_cachea(monkeypatch, tmp_path):
    llamadas = []

    def falso_get(url, timeout):
        llamadas.append(url)
        return _Respuesta(
            [
                {"casa": "blue", "compra": 1405, "venta": 1425, "fecha": "2026-02-27"},
                {"casa": "blue", "compra": None, "venta": 1400, "fecha": "2026-02-26"},
                {"casa": "blue", "compra": 1350, "venta": 1370, "fecha": "2026-01-30"},
            ]
        )

    monkeypatch.setattr(dolar.httpx, "get", falso_get)
    monkeypatch.setattr(dolar, "CACHE_DIR", tmp_path)

    filas = dolar.descargar_blue()
    assert filas == [("2026-01-30", 1350.0, 1370.0), ("2026-02-27", 1405.0, 1425.0)]

    dolar.descargar_blue()
    assert len(llamadas) == 1  # la segunda vez salió de la caché


def test_descargar_blue_sin_fecha_falla_con_keyerror(monkeypatch, tmp_path):
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta([{"compra": 1, "venta": 2}]))
    monkeypatch.setattr(dolar, "CACHE_DIR", tmp_path)
    with pytest.raises(KeyError):
        dolar.descargar_blue()


def test_descargar_blue_respuesta_que_no_es_una_lista_de_cotizaciones(monkeypatch, tmp_path):
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta({"error": "x"}))
    monkeypatch.setattr(dolar, "CACHE_DIR", tmp_path)
    with pytest.raises(AttributeError):
        dolar.descargar_blue()


def test_descargar_blue_actual_convierte_la_hora_a_hora_argentina(monkeypatch):
    respuesta = {"compra": 1520, "venta": 1540, "fechaActualizacion": "2026-10-12T20:56:00.000Z"}
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta(respuesta))
    actual = dolar.descargar_blue_actual()
    assert (actual.compra, actual.venta) == (1520.0, 1540.0)
    assert (actual.actualizado.hour, actual.actualizado.minute) == (17, 56)
    assert actual.actualizado.utcoffset() == timedelta(hours=-3)


def test_descargar_blue_actual_sin_hora_de_actualizacion_falla_con_keyerror(monkeypatch):
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta({"compra": 1, "venta": 2}))
    with pytest.raises(KeyError):
        dolar.descargar_blue_actual()


def test_descargar_cotizaciones_actuales_indexa_por_casa_y_convierte_la_hora(monkeypatch):
    respuesta = [
        {"casa": "oficial", "compra": 1485, "venta": 1535, "fechaActualizacion": "2026-10-09T18:55:00.000Z"},
        {"casa": "bolsa", "compra": 1535.9, "venta": 1542.9, "fechaActualizacion": "2026-10-12T20:56:00.000Z"},
    ]
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta(respuesta))
    cotizaciones = dolar.descargar_cotizaciones_actuales()
    assert set(cotizaciones) == {"oficial", "bolsa"}
    assert (cotizaciones["oficial"].compra, cotizaciones["oficial"].venta) == (1485.0, 1535.0)
    assert (cotizaciones["oficial"].actualizado.hour, cotizaciones["oficial"].actualizado.minute) == (15, 55)
    assert cotizaciones["bolsa"].actualizado.utcoffset() == timedelta(hours=-3)


def test_descargar_cotizaciones_actuales_sin_casa_falla_con_keyerror(monkeypatch):
    respuesta = [{"compra": 1, "venta": 2, "fechaActualizacion": "2026-10-09T18:55:00.000Z"}]
    monkeypatch.setattr(dolar.httpx, "get", lambda url, timeout: _Respuesta(respuesta))
    with pytest.raises(KeyError):
        dolar.descargar_cotizaciones_actuales()
