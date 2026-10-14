import pytest

from simulador.dominio.estrategias import (
    inflacion_acumulada,
    plazo_fijo,
    plazo_fijo_renovado,
    rendimiento_real,
    simular_plazo_fijo,
)


def test_plazo_fijo_interes_simple_a_un_anio():
    assert plazo_fijo(1000, 0.36, 365) == pytest.approx(1360)


def test_plazo_fijo_30_dias():
    # 1000 * 0.36 * 30/365 = 29.589...
    assert plazo_fijo(1000, 0.36, 30) == pytest.approx(1029.589, abs=1e-3)


def test_plazo_fijo_cero_dias_devuelve_capital():
    assert plazo_fijo(1000, 0.36, 0) == 1000


def test_plazo_fijo_rechaza_capital_negativo():
    with pytest.raises(ValueError):
        plazo_fijo(-1, 0.36, 30)


def test_renovado_capitaliza_mas_que_simple():
    simple = plazo_fijo(1000, 0.36, 360)
    renovado = plazo_fijo_renovado(1000, 0.36, 360, plazo=30)
    assert renovado > simple


def test_renovado_un_solo_tramo_equivale_a_simple():
    assert plazo_fijo_renovado(1000, 0.36, 30, plazo=30) == pytest.approx(plazo_fijo(1000, 0.36, 30))


def test_renovado_tramo_final_mas_corto():
    esperado = plazo_fijo(plazo_fijo(1000, 0.36, 30), 0.36, 10)
    assert plazo_fijo_renovado(1000, 0.36, 40, plazo=30) == pytest.approx(esperado)


def test_inflacion_acumulada_compone_no_suma():
    assert inflacion_acumulada([0.10, 0.10]) == pytest.approx(0.21)


def test_inflacion_acumulada_vacia_es_cero():
    assert inflacion_acumulada([]) == 0


def test_rendimiento_real_positivo_cuando_gana_a_la_inflacion():
    assert rendimiento_real(0.10, 0.05) == pytest.approx(0.047619, abs=1e-6)


def test_rendimiento_real_negativo_cuando_pierde():
    assert rendimiento_real(0.03, 0.05) < 0


def test_rendimiento_real_cero_cuando_empata():
    assert rendimiento_real(0.05, 0.05) == pytest.approx(0)


def test_simular_plazo_fijo_pierde_contra_inflacion_alta():
    r = simular_plazo_fijo(1_000_000, 0.30, [0.05] * 6)
    assert r.rendimiento_real < 0
    assert r.monto_final > r.capital_inicial
    assert r.monto_final_real < r.capital_inicial


def test_simular_plazo_fijo_gana_contra_inflacion_baja():
    r = simular_plazo_fijo(1_000_000, 0.40, [0.01] * 6)
    assert r.rendimiento_real > 0
    assert r.monto_final_real > r.capital_inicial
