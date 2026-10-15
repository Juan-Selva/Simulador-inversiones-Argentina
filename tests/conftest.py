from datetime import date

import pytest
from datos_de_prueba import (
    IPC_7_MESES,
    blue_actual,
    cotizaciones_actuales,
    cotizaciones_blue,
    uva_diaria,
)

from simulador import historial, servicio


@pytest.fixture(autouse=True)
def historial_aislado(tmp_path, monkeypatch):
    """Ningún test toca el historial real del usuario: cada uno usa una base en una carpeta temporal."""
    monkeypatch.setattr(historial, "RUTA", tmp_path / "historial" / "historial.db")


@pytest.fixture
def servicio_con_datos(monkeypatch):
    """Servicio con datos de prueba: hoy es 13/10/2026 y el IPC llega hasta julio."""
    monkeypatch.setattr(servicio, "_hoy", lambda: date(2026, 10, 13))
    monkeypatch.setattr(servicio, "descargar_serie", lambda serie_id, usar_cache=True: IPC_7_MESES)
    monkeypatch.setattr(servicio, "descargar_blue", lambda usar_cache=True: cotizaciones_blue())
    monkeypatch.setattr(servicio, "descargar_blue_actual", lambda: blue_actual())
    monkeypatch.setattr(servicio, "descargar_cotizaciones_actuales", lambda: cotizaciones_actuales())
    monkeypatch.setattr(servicio, "descargar_uva", lambda usar_cache=True: uva_diaria())
    return servicio
