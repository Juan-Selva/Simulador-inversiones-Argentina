import pytest

from simulador.dominio.estrategias import simular_dolar


def test_dolar_que_sube_mas_que_la_inflacion_gana_en_real():
    r = simular_dolar(1000, 1000, 1200, inflacion=0.10)
    assert r.monto_final == pytest.approx(1200)
    assert r.rendimiento_nominal == pytest.approx(0.20)
    assert r.rendimiento_real == pytest.approx(1.2 / 1.1 - 1)


def test_dolar_quieto_pierde_contra_la_inflacion():
    r = simular_dolar(1000, 1000, 1000, inflacion=0.10)
    assert r.rendimiento_nominal == pytest.approx(0)
    assert r.rendimiento_real == pytest.approx(1 / 1.1 - 1)
    assert r.monto_final_real < r.capital_inicial


def test_comprar_mas_caro_que_lo_que_se_recibe_al_vender_cuesta_spread():
    sin_spread = simular_dolar(1000, 1000, 1200, inflacion=0.10)
    con_spread = simular_dolar(1000, 1020, 1200, inflacion=0.10)
    assert con_spread.monto_final == pytest.approx(1000 / 1020 * 1200)
    assert con_spread.rendimiento_real < sin_spread.rendimiento_real


def test_dolar_rechaza_precios_invalidos():
    with pytest.raises(ValueError):
        simular_dolar(1000, 0, 1200, inflacion=0.1)
    with pytest.raises(ValueError):
        simular_dolar(1000, 1000, -5, inflacion=0.1)


def test_dolar_rechaza_capital_negativo():
    with pytest.raises(ValueError):
        simular_dolar(-1, 1000, 1200, inflacion=0.1)
