from simulador.formato import dolares, nombre_mes, pct, pesos


def test_pesos_usa_formato_argentino():
    assert pesos(1234567.891) == "$ 1.234.567,89"
    assert pesos(0) == "$ 0,00"


def test_pct_usa_coma_decimal():
    assert pct(0.1855) == "18,55 %"
    assert pct(-0.0072) == "-0,72 %"


def test_nombre_mes():
    assert nombre_mes("2026-08") == "agosto de 2026"
    assert nombre_mes("2026-01-01") == "enero de 2026"
    assert nombre_mes("2025-12") == "diciembre de 2025"


def test_dolares_usa_formato_argentino():
    assert dolares(645.1234) == "USD 645,12"
    assert dolares(1234567.5) == "USD 1.234.567,50"
