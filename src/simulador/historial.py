"""Historial de simulaciones guardadas, en una base SQLite local.

Nada se guarda solo: la simulación llega acá únicamente cuando el usuario
elige guardarla y le pone un nombre. Se guarda lo que había en el momento
(parámetros, valores y porcentajes), así que se puede volver a ver sin
depender de que las cotizaciones de hoy sigan siendo las mismas.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from simulador.ingesta.dolar import ZONA_ARGENTINA
from simulador.instantanea import NOMBRES_DE_TIPO, Instantanea

RUTA = Path.home() / ".local" / "share" / "simulador-inversiones" / "historial.db"
LARGO_MAXIMO_NOMBRE = 80

_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS simulaciones (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT NOT NULL,
    tipo       TEXT NOT NULL,
    creada     TEXT NOT NULL,   -- ISO 8601, hora argentina
    parametros TEXT NOT NULL,   -- JSON con lo que ingresó el usuario
    datos      TEXT NOT NULL,   -- JSON con el resultado crudo
    texto      TEXT NOT NULL    -- JSON: líneas tal como se vieron
)
"""


class ErrorHistorial(Exception):
    """El historial no se pudo leer o escribir, o el pedido no es válido."""


@dataclass(frozen=True)
class Registro:
    id: int
    nombre: str
    tipo: str
    creada: datetime
    parametros: dict[str, Any]
    datos: dict[str, Any]
    texto: list[str]

    @property
    def nombre_de_tipo(self) -> str:
        return NOMBRES_DE_TIPO.get(self.tipo, self.tipo)

    @property
    def fecha_legible(self) -> str:
        return self.creada.strftime("%d/%m/%Y %H:%M")


def _ahora() -> datetime:
    return datetime.now(ZONA_ARGENTINA)


def _conectar() -> sqlite3.Connection:
    try:
        RUTA.parent.mkdir(parents=True, exist_ok=True)
        conexion = sqlite3.connect(RUTA)
        conexion.execute(_CREAR_TABLA)
        return conexion
    except (OSError, sqlite3.Error) as error:
        raise ErrorHistorial(f"No se pudo abrir el historial ({error}).") from error


def _nombre_valido(nombre: str) -> str:
    nombre = " ".join(nombre.split())
    if not nombre:
        raise ErrorHistorial("Ponele un nombre a la simulación para guardarla.")
    if len(nombre) > LARGO_MAXIMO_NOMBRE:
        raise ErrorHistorial(f"El nombre es demasiado largo (máximo {LARGO_MAXIMO_NOMBRE} caracteres).")
    return nombre


def _a_registro(fila: tuple) -> Registro:
    id_, nombre, tipo, creada, parametros, datos, texto = fila
    return Registro(
        id=id_,
        nombre=nombre,
        tipo=tipo,
        creada=datetime.fromisoformat(creada),
        parametros=json.loads(parametros),
        datos=json.loads(datos),
        texto=json.loads(texto),
    )


_COLUMNAS = "id, nombre, tipo, creada, parametros, datos, texto"


def guardar(nombre: str, instantanea: Instantanea) -> Registro:
    """Guarda una simulación con el nombre elegido y devuelve el registro creado."""
    nombre = _nombre_valido(nombre)
    creada = _ahora().isoformat(timespec="seconds")
    try:
        with closing(_conectar()) as conexion, conexion:
            cursor = conexion.execute(
                "INSERT INTO simulaciones (nombre, tipo, creada, parametros, datos, texto) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    nombre,
                    instantanea.tipo,
                    creada,
                    json.dumps(instantanea.parametros, ensure_ascii=False),
                    json.dumps(instantanea.datos, ensure_ascii=False),
                    json.dumps(instantanea.texto, ensure_ascii=False),
                ),
            )
            return obtener_con(conexion, cursor.lastrowid)
    except sqlite3.Error as error:
        raise ErrorHistorial(f"No se pudo guardar la simulación ({error}).") from error


def obtener_con(conexion: sqlite3.Connection, id_: int) -> Registro:
    fila = conexion.execute(f"SELECT {_COLUMNAS} FROM simulaciones WHERE id = ?", (id_,)).fetchone()
    if fila is None:
        raise ErrorHistorial(f"No hay una simulación guardada con el número {id_}.")
    return _a_registro(fila)


def obtener(id_: int) -> Registro:
    try:
        with closing(_conectar()) as conexion:
            return obtener_con(conexion, id_)
    except sqlite3.Error as error:
        raise ErrorHistorial(f"No se pudo leer el historial ({error}).") from error


def listar() -> list[Registro]:
    """Todas las simulaciones guardadas, de la más nueva a la más vieja."""
    try:
        with closing(_conectar()) as conexion:
            filas = conexion.execute(f"SELECT {_COLUMNAS} FROM simulaciones ORDER BY creada DESC, id DESC").fetchall()
    except sqlite3.Error as error:
        raise ErrorHistorial(f"No se pudo leer el historial ({error}).") from error
    return [_a_registro(fila) for fila in filas]


def renombrar(id_: int, nombre: str) -> Registro:
    nombre = _nombre_valido(nombre)
    try:
        with closing(_conectar()) as conexion, conexion:
            obtener_con(conexion, id_)  # falla si no existe
            conexion.execute("UPDATE simulaciones SET nombre = ? WHERE id = ?", (nombre, id_))
            return obtener_con(conexion, id_)
    except sqlite3.Error as error:
        raise ErrorHistorial(f"No se pudo renombrar la simulación ({error}).") from error


def borrar(id_: int) -> None:
    try:
        with closing(_conectar()) as conexion, conexion:
            obtener_con(conexion, id_)  # falla si no existe
            conexion.execute("DELETE FROM simulaciones WHERE id = ?", (id_,))
    except sqlite3.Error as error:
        raise ErrorHistorial(f"No se pudo borrar la simulación ({error}).") from error
