"""Exportación de simulaciones a PDF.

Usa el mismo texto que se ve en pantalla y en el historial, así el PDF
muestra exactamente lo que había al momento de simular.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from simulador.historial import Registro
from simulador.ingesta.dolar import ZONA_ARGENTINA
from simulador.instantanea import NOMBRES_DE_TIPO, Instantanea

PIE = "Simulador de inversiones. Valores al momento de la simulación; no es asesoramiento financiero."
MARGEN = 18

# Las fuentes base de los PDF cubren latin-1 (tildes, ñ, « »); lo demás se reemplaza.
_REEMPLAZOS = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": "...", "•": "-",
    "→": "->", "≥": ">=", "≤": "<=", " ": " ",
}  # fmt: skip

_VEREDICTOS = ("Mejor en términos reales", "Resultado con tu plazo fijo", "La opción más barata")


class ErrorExportacion(Exception):
    """No se pudo generar o escribir el PDF."""


def _ahora() -> datetime:
    return datetime.now(ZONA_ARGENTINA)


def _latin1(texto: str) -> str:
    for original, reemplazo in _REEMPLAZOS.items():
        texto = texto.replace(original, reemplazo)
    return texto.encode("latin-1", "replace").decode("latin-1")


def nombre_de_archivo(nombre: str, id_: int | None = None) -> str:
    """'Plazo fijo de marzo' -> 'plazo-fijo-de-marzo' (con el número delante si se lo pasa)."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")[:50].strip("-") or "simulacion"
    return f"{id_}-{slug}" if id_ is not None else slug


class _Documento(FPDF):
    def footer(self) -> None:  # lo llama fpdf al cerrar cada página
        self.set_y(-14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(130)
        self.cell(0, 5, _latin1(PIE), align="L")
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")


def crear_pdf(titulo: str, subtitulo: str, lineas: list[str], ruta: Path) -> Path:
    """Escribe el PDF y devuelve la ruta final (se le agrega .pdf si no la tenía)."""
    ruta = Path(ruta)
    if ruta.suffix.lower() != ".pdf":
        ruta = ruta.with_name(ruta.name + ".pdf")

    pdf = _Documento(format="A4")
    pdf.alias_nb_pages()
    pdf.set_compression(False)  # PDFs de una página o dos: pesan poco y el texto queda legible para tests
    pdf.set_margins(MARGEN, MARGEN, MARGEN)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_title(_latin1(titulo))
    pdf.set_author("Simulador de inversiones")
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20)
    pdf.multi_cell(0, 9, _latin1(titulo), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(110)
    pdf.multi_cell(0, 6, _latin1(subtitulo), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 2
    pdf.set_draw_color(200)
    pdf.line(MARGEN, y, pdf.w - MARGEN, y)
    pdf.ln(7)

    for linea in lineas:
        if not linea.strip():
            pdf.ln(3)
            continue
        sangria = len(linea) - len(linea.lstrip(" "))
        destacada = linea.rstrip().endswith(":") or linea.startswith(_VEREDICTOS)
        pdf.set_font("Helvetica", "B" if destacada else "", 11)
        pdf.set_text_color(20)
        pdf.set_x(MARGEN + sangria * 1.5)
        pdf.multi_cell(0, 6, _latin1(linea.strip()), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1.5)

    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(ruta))
    except OSError as error:
        raise ErrorExportacion(f"No se pudo escribir el PDF en {ruta} ({error}).") from error
    return ruta


def exportar_instantanea(titulo: str, foto: Instantanea, ruta: Path) -> Path:
    """PDF de una simulación recién calculada (haya o no sido guardada)."""
    subtitulo = f"{NOMBRES_DE_TIPO.get(foto.tipo, foto.tipo)} - generado el {_ahora().strftime('%d/%m/%Y %H:%M')}"
    return crear_pdf(titulo, subtitulo, foto.texto, ruta)


def exportar_registro(registro: Registro, ruta: Path) -> Path:
    """PDF de una simulación del historial, con los valores del día en que se guardó."""
    subtitulo = f"{registro.nombre_de_tipo} - guardada el {registro.fecha_legible}"
    return crear_pdf(registro.nombre, subtitulo, registro.texto, ruta)
