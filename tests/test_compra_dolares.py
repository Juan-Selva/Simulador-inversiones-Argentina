import pytest

from simulador.dominio.compra_dolares import (
    CANALES,
    Cargo,
    cargos_del_canal,
    dolares_obtenidos,
    precio_efectivo,
)


def _canal(clave):
    return next(c for c in CANALES if c.clave == clave)


def test_precio_efectivo_sin_cargos_es_el_precio_de_lista():
    assert precio_efectivo(1500, ()) == 1500


def test_precio_efectivo_suma_los_cargos_sobre_el_monto_en_pesos():
    cargos = (Cargo("A", 0.30), Cargo("B", 0.005))
    assert precio_efectivo(1000, cargos) == pytest.approx(1305)


def test_precio_efectivo_rechaza_precio_no_positivo():
    with pytest.raises(ValueError):
        precio_efectivo(0, ())


def test_dolares_obtenidos():
    assert dolares_obtenidos(1_000_000, 1250) == pytest.approx(800)


@pytest.mark.parametrize("pesos, precio", [(0, 1000), (-5, 1000), (1000, 0)])
def test_dolares_obtenidos_rechaza_valores_no_positivos(pesos, precio):
    with pytest.raises(ValueError):
        dolares_obtenidos(pesos, precio)


def test_la_comision_del_broker_solo_se_suma_en_los_canales_con_broker():
    assert cargos_del_canal(_canal("mep"), 0.005)[-1] == Cargo("Comisión del broker", 0.005)
    assert cargos_del_canal(_canal("ccl"), 0.005)[-1].tasa == 0.005
    assert cargos_del_canal(_canal("blue"), 0.005) == ()
    assert cargos_del_canal(_canal("oficial"), 0.005) == ()


def test_sin_comision_no_se_agrega_ningun_cargo():
    assert cargos_del_canal(_canal("mep"), 0.0) == ()


def test_reglas_relevadas_del_catalogo():
    # Percepción del 30 % eliminada para el dólar ahorro; vigente solo en el dólar tarjeta.
    assert _canal("oficial").cargos == ()
    assert _canal("blue").cargos == ()
    assert _canal("cripto").cargos == ()
    assert [c.tasa for c in _canal("tarjeta").cargos] == [0.30]
    assert [c.clave for c in CANALES if not c.para_ahorrar] == ["tarjeta"]


def test_las_claves_de_los_canales_no_se_repiten_y_todos_tienen_notas():
    claves = [c.clave for c in CANALES]
    assert len(claves) == len(set(claves))
    assert all(c.notas for c in CANALES)
