"""
conftest.py — Configuración de pytest y fixtures para servicio-inventario.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

# Asegura que servicio-inventario/ esté en sys.path
SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from database import get_connection, init_db
from models import CREATE_PRODUCTS_TABLE_SQL


@pytest.fixture
def empty_db(tmp_path):
    """Crea una base de datos temporal con el esquema pero sin datos semilla."""
    db_file = tmp_path / "test_empty.db"
    conn = get_connection(db_file)
    with conn:
        conn.executescript(CREATE_PRODUCTS_TABLE_SQL)
    conn.close()
    return db_file


@pytest.fixture
def seeded_db(tmp_path):
    """Crea una base de datos temporal con esquema y datos semilla cargados."""
    db_file = tmp_path / "test_seeded.db"
    init_db(db_file)
    return db_file
