"""
Configuración de pytest y fixtures para servicio-pedidos.
"""
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Asegura que servicio-pedidos/ esté en sys.path
SERVICE_DIR = Path(__file__).resolve().parent.parent
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

import config
from database import get_connection, get_db, init_db
from main import app


@pytest.fixture
def temp_db(tmp_path):
    """Crea una base de datos temporal SQLite con el esquema inicializado."""
    db_file = tmp_path / "test_pedidos.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def client(temp_db):
    """
    Cliente de pruebas de FastAPI con la base de datos redirigida a un archivo temporal.
    """
    def override_get_db():
        conn = get_connection(temp_db)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
