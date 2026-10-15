from datetime import datetime

import pytest

from simulador import historial, instantanea
from simulador.historial import ErrorHistorial
from simulador.ingesta.dolar import ZONA_ARGENTINA


def _foto(tipo=instantanea.COMPARACION, texto=None, datos=None):
    return instantanea.Instantanea(
        tipo=tipo,
        parametros={"capital": 1_000_000.0, "tna": 35.0},
        datos=datos or {"mejor": "Plazo fijo", "valor": 1.5},
        texto=texto or ["línea uno", "línea dos con ñ y tilde á"],
    )


def _en(dia, hora=12):
    return lambda: datetime(2026, 10, dia, hora, 30, tzinfo=ZONA_ARGENTINA)


def test_no_guarda_nada_por_si_solo():
    assert historial.listar() == []


def test_guardar_y_obtener_conserva_todo_lo_que_se_vio(monkeypatch):
    monkeypatch.setattr(historial, "_ahora", _en(14, 15))
    guardado = historial.guardar("Mi plazo fijo", _foto())
    leido = historial.obtener(guardado.id)

    assert leido == guardado
    assert leido.nombre == "Mi plazo fijo"
    assert leido.tipo == instantanea.COMPARACION
    assert leido.nombre_de_tipo == "Comparación de estrategias"
    assert leido.creada == datetime(2026, 10, 14, 15, 30, tzinfo=ZONA_ARGENTINA)
    assert leido.fecha_legible == "14/10/2026 15:30"
    assert leido.parametros == {"capital": 1_000_000.0, "tna": 35.0}
    assert leido.datos == {"mejor": "Plazo fijo", "valor": 1.5}
    assert leido.texto == ["línea uno", "línea dos con ñ y tilde á"]


def test_listar_ordena_de_la_mas_nueva_a_la_mas_vieja(monkeypatch):
    for dia, nombre in ((10, "vieja"), (12, "nueva"), (11, "del medio")):
        monkeypatch.setattr(historial, "_ahora", _en(dia))
        historial.guardar(nombre, _foto())
    assert [r.nombre for r in historial.listar()] == ["nueva", "del medio", "vieja"]


def test_el_nombre_se_limpia_y_no_puede_estar_vacio():
    assert historial.guardar("  Mi   compra  ", _foto()).nombre == "Mi compra"
    for malo in ("", "   "):
        with pytest.raises(ErrorHistorial, match="nombre"):
            historial.guardar(malo, _foto())
    with pytest.raises(ErrorHistorial, match="largo"):
        historial.guardar("x" * (historial.LARGO_MAXIMO_NOMBRE + 1), _foto())
    assert len(historial.listar()) == 1  # los rechazados no se guardaron


def test_se_pueden_repetir_nombres():
    historial.guardar("igual", _foto())
    historial.guardar("igual", _foto())
    assert len(historial.listar()) == 2


def test_renombrar_cambia_solo_el_nombre(monkeypatch):
    monkeypatch.setattr(historial, "_ahora", _en(13))
    original = historial.guardar("viejo", _foto())
    nuevo = historial.renombrar(original.id, "  nuevo nombre ")
    assert nuevo.nombre == "nuevo nombre"
    assert (nuevo.creada, nuevo.texto, nuevo.datos, nuevo.parametros) == (
        original.creada,
        original.texto,
        original.datos,
        original.parametros,
    )
    with pytest.raises(ErrorHistorial):
        historial.renombrar(original.id, "")
    assert historial.obtener(original.id).nombre == "nuevo nombre"


def test_borrar_saca_solo_esa_simulacion():
    a = historial.guardar("a", _foto())
    b = historial.guardar("b", _foto())
    historial.borrar(a.id)
    assert [r.id for r in historial.listar()] == [b.id]


def test_id_inexistente_da_un_error_claro():
    for accion in (historial.obtener, historial.borrar, lambda i: historial.renombrar(i, "x")):
        with pytest.raises(ErrorHistorial, match="99"):
            accion(99)


def test_los_ids_no_se_reutilizan_despues_de_borrar():
    a = historial.guardar("a", _foto())
    historial.borrar(a.id)
    assert historial.guardar("b", _foto()).id != a.id


def test_si_no_se_puede_abrir_la_base_avisa(monkeypatch, tmp_path):
    archivo = tmp_path / "es_un_archivo"
    archivo.write_text("x")
    monkeypatch.setattr(historial, "RUTA", archivo / "historial.db")  # "carpeta" que es un archivo
    with pytest.raises(ErrorHistorial, match="historial"):
        historial.listar()
