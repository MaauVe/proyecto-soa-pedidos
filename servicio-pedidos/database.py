"""
Motor de base de datos y gestión de conexiones SQLite para servicio-pedidos.
Aislado e independiente: pedidos.db dentro de servicio-pedidos/.
"""
import logging
import sqlite3
from pathlib import Path
from typing import Generator, Union

from config import DB_PATH
from models import CREATE_SCHEMA_SQL

logger = logging.getLogger("servicio-pedidos.database")


def get_connection(db_path: Union[Path, str] = DB_PATH) -> sqlite3.Connection:
    """
    Crea y retorna una conexión SQLite configurada con row_factory y foreign keys activos.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Union[Path, str] = DB_PATH) -> None:
    """
    Crea el esquema de la base de datos (orders y order_items) si no existe.
    Se ejecuta al arranque del servicio (lifespan).
    No inserta datos semilla: la base de datos arranca vacía.
    """
    logger.info("Inicializando base de datos en: %s", db_path)
    conn = get_connection(db_path)
    try:
        with conn:
            conn.executescript(CREATE_SCHEMA_SQL)
        logger.info("Base de datos de pedidos inicializada correctamente.")
    finally:
        conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """
    Dependencia de FastAPI: provee una conexión SQLite por request
    y garantiza su cierre seguro al finalizar la respuesta.
    """
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
