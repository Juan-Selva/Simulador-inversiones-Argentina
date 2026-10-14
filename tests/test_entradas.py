import pytest

from simulador.interfaz.entradas import parsear_entero, parsear_numero


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("1.000.000", 1_000_000),
        ("1000000", 1_000_000),
        ("35", 35),
        ("35,5", 35.5),
        ("35.5", 35.5),
        ("1.000,50", 1000.5),
        ("$ 2.500", 2500),
        ("0.125", 0.125),
        ("3,5 %", 3.5),
        ("1.000", 1000),
        ("-5", -5),
    ],
)
def test_parsear_numero_formatos_argentinos(texto, esperado):
    assert parsear_numero(texto) == pytest.approx(esperado)


@pytest.mark.parametrize("texto", ["", "   ", "abc", "1,2,3", "nan", "inf", "$"])
def test_parsear_numero_rechaza_lo_que_no_es_un_numero(texto):
    with pytest.raises(ValueError):
        parsear_numero(texto)


def test_parsear_entero():
    assert parsear_entero("6") == 6
    assert parsear_entero("1.000") == 1000


def test_parsear_entero_rechaza_decimales():
    with pytest.raises(ValueError, match="entero"):
        parsear_entero("6,5")
