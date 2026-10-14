import json

import pytest

from simulador import preferencias


@pytest.fixture(autouse=True)
def ruta_temporal(monkeypatch, tmp_path):
    """Los tests nunca tocan las preferencias reales del usuario."""
    monkeypatch.setattr(preferencias, "RUTA", tmp_path / "config" / "preferencias.json")


def test_sin_archivo_se_sigue_al_sistema():
    assert preferencias.cargar_modo() == "system"


@pytest.mark.parametrize("modo", ["system", "light", "dark"])
def test_guardar_y_volver_a_cargar(modo):
    assert preferencias.guardar_modo(modo) is True
    assert preferencias.cargar_modo() == modo


def test_guardar_crea_la_carpeta_de_configuracion():
    preferencias.guardar_modo("dark")
    assert preferencias.RUTA.exists()


@pytest.mark.parametrize(
    "contenido",
    ["no es json", "[]", '"dark"', '{"tema": "violeta"}', '{"tema": null}', '{"tema": ["dark"]}', "{}"],
)
def test_un_archivo_roto_o_con_valor_desconocido_vuelve_al_defecto(contenido):
    preferencias.RUTA.parent.mkdir(parents=True)
    preferencias.RUTA.write_text(contenido, encoding="utf-8")
    assert preferencias.cargar_modo() == "system"


def test_guardar_conserva_otras_preferencias():
    preferencias.RUTA.parent.mkdir(parents=True)
    preferencias.RUTA.write_text(json.dumps({"otra": 1}), encoding="utf-8")
    preferencias.guardar_modo("light")
    assert json.loads(preferencias.RUTA.read_text(encoding="utf-8")) == {"otra": 1, "tema": "light"}


def test_guardar_un_tema_desconocido_falla():
    with pytest.raises(ValueError):
        preferencias.guardar_modo("violeta")


def test_si_no_se_puede_escribir_devuelve_false_sin_romper(monkeypatch, tmp_path):
    archivo = tmp_path / "archivo"
    archivo.write_text("x")
    monkeypatch.setattr(preferencias, "RUTA", archivo / "preferencias.json")  # "carpeta" que es un archivo
    assert preferencias.guardar_modo("dark") is False
    assert preferencias.cargar_modo() == "system"
