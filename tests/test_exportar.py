import re
from datetime import datetime

import pytest

from simulador import cli, exportar, historial, instantanea
from simulador.exportar import ErrorExportacion
from simulador.ingesta.dolar import ZONA_ARGENTINA

from typer.testing import CliRunner

runner = CliRunner()


def _texto_del_pdf(ruta) -> str:
    """El PDF se escribe sin comprimir y con fuentes base: el texto queda como latin-1 legible."""
    return ruta.read_bytes().decode("latin-1")


def test_crear_pdf_escribe_un_pdf_con_titulo_subtitulo_y_lineas(tmp_path):
    ruta = exportar.crear_pdf("Mi simulación", "Plazo fijo - guardada hoy", ["Capital $ 1.000", "", "  sangrada ñandú"], tmp_path / "a.pdf")
    datos = ruta.read_bytes()
    assert datos.startswith(b"%PDF-") and datos.rstrip().endswith(b"%%EOF")
    texto = _texto_del_pdf(ruta)
    for esperado in ("Mi simulación", "Plazo fijo - guardada hoy", "Capital $ 1.000", "sangrada ñandú", "no es asesoramiento financiero"):
        assert esperado in texto


def test_agrega_la_extension_pdf_y_crea_carpetas(tmp_path):
    ruta = exportar.crear_pdf("x", "y", ["z"], tmp_path / "nueva" / "sin_extension")
    assert ruta == tmp_path / "nueva" / "sin_extension.pdf" and ruta.exists()


def test_caracteres_fuera_de_latin1_no_rompen_el_pdf(tmp_path):
    ruta = exportar.crear_pdf("Título — largo", "sub", ["flecha → y “comillas” y emoji 😀"], tmp_path / "b.pdf")
    texto = _texto_del_pdf(ruta)
    assert "Título - largo" in texto and "flecha -> y" in texto and '"comillas"' in texto


def test_un_texto_largo_pasa_a_una_segunda_pagina(tmp_path):
    ruta = exportar.crear_pdf("Largo", "sub", [f"Línea número {i}" for i in range(120)], tmp_path / "c.pdf")
    paginas = int(re.search(r"/Count (\d+)", _texto_del_pdf(ruta)).group(1))
    assert paginas >= 2


def test_si_no_se_puede_escribir_avisa(tmp_path):
    ocupado = tmp_path / "archivo"
    ocupado.write_text("x")
    with pytest.raises(ErrorExportacion, match="No se pudo escribir"):
        exportar.crear_pdf("x", "y", ["z"], ocupado / "adentro.pdf")  # "carpeta" que es un archivo


@pytest.mark.parametrize(
    "nombre, id_, esperado",
    [
        ("Plazo fijo de marzo", None, "plazo-fijo-de-marzo"),
        ("  Comparación: ¡año 2026!  ", 4, "4-comparacion-ano-2026"),
        ("???", 2, "2-simulacion"),
        ("x" * 200, None, "x" * 50),
    ],
)
def test_nombre_de_archivo(nombre, id_, esperado):
    assert exportar.nombre_de_archivo(nombre, id_) == esperado


def test_exportar_instantanea_y_registro(servicio_con_datos, tmp_path, monkeypatch):
    monkeypatch.setattr(exportar, "_ahora", lambda: datetime(2026, 10, 15, 9, 5, tzinfo=ZONA_ARGENTINA))
    c = servicio_con_datos.comparar_estrategias(1_000_000, 35, 6)
    foto = instantanea.de_comparacion(1_000_000, 35, 6, c)

    ruta = exportar.exportar_instantanea("Seis meses", foto, tmp_path / "foto.pdf")
    texto = _texto_del_pdf(ruta)
    assert "Seis meses" in texto and "generado el 15/10/2026 09:05" in texto
    assert "Mejor en términos reales: Dólar blue." in texto
    assert r"UVA \(cierre de mes\)" in texto  # los paréntesis van escapados en el PDF

    registro = historial.guardar("Guardada", foto)
    ruta = exportar.exportar_registro(registro, tmp_path / "registro.pdf")
    texto = _texto_del_pdf(ruta)
    assert "Guardada" in texto and "Comparación de estrategias - guardada el" in texto
    assert "Mejor en términos reales: Dólar blue." in texto


# --- CLI -------------------------------------------------------------------------

def test_cli_historial_exportar(servicio_con_datos, tmp_path, monkeypatch):
    runner.invoke(cli.app, ["comparar", "--capital", "1000000", "--tna", "35", "--meses", "6", "--guardar", "Mi análisis"])
    destino = tmp_path / "salida.pdf"
    r = runner.invoke(cli.app, ["historial", "exportar", "1", "--salida", str(destino)])
    assert r.exit_code == 0, r.output
    assert "PDF guardado en:" in r.output and destino.exists()
    assert "Mi análisis" in _texto_del_pdf(destino)

    # sin --salida: archivo con el nombre de la simulación en la carpeta actual
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli.app, ["historial", "exportar", "1"])
    assert r.exit_code == 0 and (tmp_path / "1-mi-analisis.pdf").exists()


def test_cli_historial_exportar_numero_inexistente():
    r = runner.invoke(cli.app, ["historial", "exportar", "9"])
    assert r.exit_code == 1 and "9" in r.output


@pytest.mark.parametrize(
    "comando",
    [
        ["comparar", "--capital", "1000000", "--tna", "35", "--meses", "6"],
        ["plazo-fijo", "--capital", "1000000", "--tna", "35", "--meses", "6"],
        ["comprar-dolares", "--pesos", "1000000"],
        ["contado-o-cuotas", "--precio", "120000", "--cuotas", "6", "--tna", "35", "--descuento", "10"],
    ],
)
def test_cli_pdf_en_cada_simulacion_sin_guardar(servicio_con_datos, tmp_path, comando):
    destino = tmp_path / "resultado.pdf"
    r = runner.invoke(cli.app, [*comando, "--pdf", str(destino)])
    assert r.exit_code == 0, r.output
    assert destino.exists() and "PDF guardado en:" in r.output
    assert historial.listar() == []  # exportar no guarda en el historial


def test_cli_pdf_usa_el_nombre_de_guardar_como_titulo(servicio_con_datos, tmp_path):
    destino = tmp_path / "r.pdf"
    r = runner.invoke(cli.app, ["plazo-fijo", "--capital", "1000", "--tna", "35", "--meses", "1", "--inflacion-mensual", "2", "--guardar", "Mi plazo", "--pdf", str(destino)])
    assert r.exit_code == 0
    assert "Mi plazo" in _texto_del_pdf(destino) and len(historial.listar()) == 1


def test_cli_pdf_en_ruta_imposible_avisa(servicio_con_datos, tmp_path):
    ocupado = tmp_path / "archivo"
    ocupado.write_text("x")
    r = runner.invoke(cli.app, ["comprar-dolares", "--pesos", "1000", "--pdf", str(ocupado / "x.pdf")])
    assert r.exit_code == 1 and "No se pudo escribir" in r.output
