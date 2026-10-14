import pytest

from simulador.ingesta import series
from simulador.ingesta.series import (
    mes_anterior,
    ultimas_variaciones,
    valor_del_mes,
    variaciones_mensuales,
)

NIVELES = [
    ("2026-01-01", 100.0),
    ("2026-02-01", 102.0),
    ("2026-03-01", 104.04),
    ("2026-04-01", 106.1208),
]


def test_variaciones_mensuales():
    assert variaciones_mensuales(NIVELES) == pytest.approx([0.02, 0.02, 0.02])


def test_ultimas_variaciones_devuelve_los_ultimos_meses_con_su_fecha():
    resultado = ultimas_variaciones(NIVELES, 2)
    assert [fecha for fecha, _ in resultado] == ["2026-03-01", "2026-04-01"]
    assert [v for _, v in resultado] == pytest.approx([0.02, 0.02])


def test_ultimas_variaciones_todos_los_meses_posibles():
    assert len(ultimas_variaciones(NIVELES, 3)) == 3


def test_ultimas_variaciones_falla_si_faltan_datos():
    with pytest.raises(ValueError):
        ultimas_variaciones(NIVELES, 4)


def test_ultimas_variaciones_rechaza_meses_invalidos():
    with pytest.raises(ValueError):
        ultimas_variaciones(NIVELES, 0)


def test_mes_anterior():
    assert mes_anterior("2026-08-01") == "2026-07"
    assert mes_anterior("2026-01-01") == "2025-12"


def test_valor_del_mes_encuentra_el_mes():
    assert valor_del_mes(NIVELES, "2026-03") == 104.04


def test_valor_del_mes_falla_si_no_esta():
    with pytest.raises(ValueError):
        valor_del_mes(NIVELES, "2025-12")


class _Respuesta:
    def raise_for_status(self):
        pass

    def json(self):
        return {"data": [["2026-02-01", 20.0], ["2026-01-01", 10.0], ["2026-03-01", None]]}


def test_descargar_serie_ordena_filtra_vacios_y_cachea(monkeypatch, tmp_path):
    llamadas = []

    def falso_get(url, params, timeout):
        llamadas.append(params)
        return _Respuesta()

    monkeypatch.setattr(series.httpx, "get", falso_get)
    monkeypatch.setattr(series, "CACHE_DIR", tmp_path)

    filas = series.descargar_serie("abc")
    assert filas == [("2026-01-01", 10.0), ("2026-02-01", 20.0)]
    assert llamadas[0]["ids"] == "abc"

    series.descargar_serie("abc")
    assert len(llamadas) == 1  # la segunda vez salió de la caché
