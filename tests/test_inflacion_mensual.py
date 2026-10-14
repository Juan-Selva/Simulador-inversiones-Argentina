from datetime import date

import pytest
from datos_de_prueba import IPC_20_MESES

from simulador.ingesta.series import (
    mes_pasado,
    ultimo_mes,
    variacion_del_mes,
    variacion_interanual,
)


def test_mes_pasado():
    assert mes_pasado(date(2026, 10, 13)) == "2026-09"
    assert mes_pasado(date(2026, 1, 5)) == "2025-12"


def test_ultimo_mes():
    assert ultimo_mes(IPC_20_MESES) == "2026-08"


def test_ultimo_mes_de_serie_vacia_falla():
    with pytest.raises(ValueError):
        ultimo_mes([])


def test_variacion_del_mes():
    assert variacion_del_mes(IPC_20_MESES, "2026-03") == pytest.approx(0.02)


def test_variacion_del_primer_mes_falla_porque_no_hay_anterior():
    with pytest.raises(ValueError):
        variacion_del_mes(IPC_20_MESES, "2025-01")


def test_variacion_de_un_mes_inexistente_falla():
    with pytest.raises(ValueError):
        variacion_del_mes(IPC_20_MESES, "2030-01")


def test_variacion_interanual():
    assert variacion_interanual(IPC_20_MESES, "2026-08") == pytest.approx(1.02**12 - 1)


def test_variacion_interanual_sin_dato_del_anio_anterior_falla():
    with pytest.raises(ValueError):
        variacion_interanual(IPC_20_MESES, "2025-08")
