import pytest

from simulador.dominio.estrategias import simular_uva
from simulador.ingesta import uva


def test_simular_uva_ajusta_el_capital_por_la_variacion_de_la_uva():
    r = simular_uva(1_000_000, 1800.05, 2096.27, inflacion=0.1480)
    assert r.monto_final == pytest.approx(1_164_556, rel=1e-5)
    assert r.rendimiento_nominal == pytest.approx(0.16456, abs=1e-4)
    assert r.rendimiento_real == pytest.approx((1.16456 / 1.148) - 1, abs=1e-4)


def test_simular_uva_valida_entradas():
    with pytest.raises(ValueError):
        simular_uva(-1, 1, 1, 0)
    with pytest.raises(ValueError):
        simular_uva(1, 0, 1, 0)


def test_cierres_mensuales_toma_el_ultimo_dia_de_cada_mes():
    filas = [("2026-01-10", 1.0), ("2026-01-28", 2.0), ("2026-02-03", 3.0)]
    assert uva.cierres_mensuales(filas) == [("2026-01", 2.0), ("2026-02", 3.0)]


class _Resp:
    def __init__(self, datos):
        self._d = datos

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_descargar_uva_ordena_filtra_vacios_y_cachea(monkeypatch, tmp_path):
    monkeypatch.setattr(uva, "CACHE_DIR", tmp_path)
    llamadas = []

    def get(url, timeout):
        llamadas.append(url)
        return _Resp([
            {"fecha": "2026-01-02", "valor": 2},
            {"fecha": "2026-01-01", "valor": "1.5"},
            {"fecha": "2026-01-03", "valor": None},
        ])

    monkeypatch.setattr(uva.httpx, "get", get)
    esperado = [("2026-01-01", 1.5), ("2026-01-02", 2.0)]
    assert uva.descargar_uva() == esperado
    assert uva.descargar_uva() == esperado  # segunda vez, desde caché
    assert len(llamadas) == 1
