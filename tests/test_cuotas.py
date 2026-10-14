import pytest

from simulador.dominio.cuotas import (
    precio_de_contado,
    tasa_de_equilibrio,
    tasa_mensual_de_tna,
    tna_de_tasa_mensual,
    valor_presente_de_cuotas,
)


def test_precio_de_contado_con_y_sin_descuento():
    assert precio_de_contado(1000, 0.10) == pytest.approx(900)
    assert precio_de_contado(1000) == 1000


def test_tasa_mensual_de_tna_es_la_de_un_plazo_fijo_a_30_dias():
    assert tasa_mensual_de_tna(0.36) == pytest.approx(0.36 * 30 / 365)
    assert tna_de_tasa_mensual(tasa_mensual_de_tna(0.36)) == pytest.approx(0.36)


def test_valor_presente_sin_rendimiento_es_el_precio_de_lista():
    assert valor_presente_de_cuotas(1000, 4, 0.0) == pytest.approx(1000)


def test_valor_presente_de_una_sola_cuota_se_descuenta_un_mes():
    assert valor_presente_de_cuotas(1000, 1, 0.10) == pytest.approx(1000 / 1.10)


def test_valor_presente_de_dos_cuotas_a_mano():
    # 500 al mes 1 y 500 al mes 2, al 5 % mensual.
    esperado = 500 / 1.05 + 500 / 1.05**2
    assert valor_presente_de_cuotas(1000, 2, 0.05) == pytest.approx(esperado)


def test_valor_presente_baja_cuando_la_plata_rinde_mas():
    assert valor_presente_de_cuotas(1000, 6, 0.04) < valor_presente_de_cuotas(1000, 6, 0.02)


def test_valor_presente_con_deflacion_es_mayor_al_precio():
    assert valor_presente_de_cuotas(1000, 3, -0.01) > 1000


def test_tasa_de_equilibrio_de_una_cuota_tiene_formula_cerrada():
    # Pagar 1000 en un mes o 900 hoy: 900 * (1 + r) = 1000.
    assert tasa_de_equilibrio(1000, 1, 0.10) == pytest.approx(1000 / 900 - 1)


def test_tasa_de_equilibrio_vuelve_al_descuento_que_la_origino():
    # Descuento que corresponde exactamente a un 5 % mensual con 2 cuotas.
    contado = 500 / 1.05 + 500 / 1.05**2
    descuento = 1 - contado / 1000
    assert tasa_de_equilibrio(1000, 2, descuento) == pytest.approx(0.05, abs=1e-9)


def test_a_la_tasa_de_equilibrio_el_valor_presente_iguala_al_contado():
    r = tasa_de_equilibrio(120_000, 6, 0.10)
    assert valor_presente_de_cuotas(120_000, 6, r) == pytest.approx(precio_de_contado(120_000, 0.10), rel=1e-9)


def test_mas_descuento_exige_que_la_plata_rinda_mas_para_preferir_cuotas():
    assert tasa_de_equilibrio(1000, 6, 0.20) > tasa_de_equilibrio(1000, 6, 0.10)


def test_sin_descuento_la_tasa_de_equilibrio_es_cero():
    assert tasa_de_equilibrio(1000, 6, 0) == 0


def test_descuento_enorme_igual_converge():
    assert tasa_de_equilibrio(1000, 1, 0.999) == pytest.approx(1 / 0.001 - 1, rel=1e-9)


@pytest.mark.parametrize(
    "precio, cuotas, descuento",
    [(0, 3, 0), (-5, 3, 0), (1000, 0, 0), (1000, 2.5, 0), (1000, 3, -0.1), (1000, 3, 1)],
)
def test_parametros_invalidos(precio, cuotas, descuento):
    with pytest.raises(ValueError):
        tasa_de_equilibrio(precio, cuotas, descuento)


def test_tasa_mensual_invalida():
    with pytest.raises(ValueError):
        valor_presente_de_cuotas(1000, 3, -1)
