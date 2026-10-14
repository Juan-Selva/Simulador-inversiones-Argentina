"""Preferencias del usuario que se guardan entre sesiones (por ahora, el tema de la interfaz).

Se guardan en un JSON chico en la carpeta de configuración del usuario. Un
archivo que falta, está roto o tiene un valor desconocido nunca rompe la
aplicación: se usa el valor por defecto.
"""

from __future__ import annotations

import json
from pathlib import Path

RUTA = Path.home() / ".config" / "simulador-inversiones" / "preferencias.json"

# Los valores que entiende CustomTkinter en set_appearance_mode.
MODOS = ("system", "light", "dark")
MODO_POR_DEFECTO = "system"


def _leer() -> dict:
    try:
        datos = json.loads(RUTA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return datos if isinstance(datos, dict) else {}


def cargar_modo() -> str:
    """Tema guardado ('system', 'light' o 'dark'); 'system' si no hay uno válido."""
    modo = _leer().get("tema")
    return modo if modo in MODOS else MODO_POR_DEFECTO


def guardar_modo(modo: str) -> bool:
    """Guarda el tema. Devuelve False si no se pudo escribir el archivo (no es grave)."""
    if modo not in MODOS:
        raise ValueError(f"Tema desconocido: {modo!r}")
    datos = _leer()
    datos["tema"] = modo
    try:
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        RUTA.write_text(json.dumps(datos), encoding="utf-8")
    except OSError:
        return False
    return True
