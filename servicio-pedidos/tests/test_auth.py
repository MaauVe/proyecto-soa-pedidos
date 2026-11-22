"""
Tests consolidados para el Bloque 1 de servicio-pedidos.
Cubre:
- T-14: Estructura base del proyecto y configuración (RNF-3, RNF-5, RNF-6).
- T-15: Esquema SQLite de orders y order_items sin datos semilla (RF-3.4, RNF-7).
- T-16: Autenticación X-API-Key y endpoint público GET /health (RF-1, RF-2, CF-1, CF-2).
"""
import sqlite3
from pathlib import Path

import pytest
from fastapi import Depends, HTTPException

import config
from auth import verify_api_key
import clients
from database import get_connection, init_db
from main import app
from schemas import HealthResponse

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida-prueba"


# Endpoint de prueba protegido para validar verify_api_key vía TestClient
@app.get("/test-protected", tags=["Test"])
def _test_protected_route(_: str = Depends(verify_api_key)):
    return {"message": "acceso permitido"}


# ── T-14: Estructura y Configuración ──────────────────────────────────────────

class TestConfigAndStructure:
    def test_api_key_loaded_from_env(self):
        """API_KEY se carga desde el .env y no está vacía."""
        assert config.API_KEY, "API_KEY no fue cargada desde .env"
        assert config.API_KEY == "changeme-local-key"

    def test_port_pedidos_config(self):
        """El puerto configurado debe ser 8004."""
        assert config.PORT == 8004
        assert config.PORT_PEDIDOS == 8004

    def test_upstream_urls_config(self):
        """Las URLs de clientes, inventario y envíos se cargan correctamente."""
        assert "8001" in config.URL_CLIENTES
        assert "8002" in config.URL_INVENTARIO
        assert "8003" in config.URL_ENVIOS
        assert "8004" in config.URL_PEDIDOS

    def test_timeout_seconds_config(self):
        """HTTP_TIMEOUT_SECONDS debe cargarse como float (10.0 por defecto)."""
        assert isinstance(config.HTTP_TIMEOUT_SECONDS, float)
        assert config.HTTP_TIMEOUT_SECONDS == 10.0

    def test_clients_module_stubs_exist(self):
        """El módulo clients.py expone las funciones requeridas para la orquestación."""
        expected_functions = [
            "validate_customer",
            "reserve_stock",
            "release_stock",
            "quote_shipment",
            "create_shipment",
            "get_shipment",
            "cancel_shipment",
        ]
        for fn_name in expected_functions:
            assert hasattr(clients, fn_name), f"Falta la función {fn_name} en clients.py"
            assert callable(getattr(clients, fn_name))

    def test_fastapi_app_metadata(self):
        """La app FastAPI tiene los metadatos y documentación habilitada."""
        assert app.title == "Servicio Orquestador de Pedidos"
        assert app.version == "0.1.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"


# ── T-15: Esquema SQLite (orders y order_items) ────────────────────────────────

class TestDatabaseSchema:
    def test_init_db_creates_tables(self, temp_db):
        """Verifica que init_db crea las tablas orders y order_items."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()

        assert "orders" in tables
        assert "order_items" in tables

    def test_orders_columns(self, temp_db):
        """Verifica las 11 columnas exactas de la tabla orders según la spec §6."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(orders);")
        columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            "id": "INTEGER",
            "customer_id": "INTEGER",
            "customer_name": "TEXT",
            "coverage_zone": "TEXT",
            "shipping_cost": "REAL",
            "total_amount": "REAL",
            "status": "TEXT",
            "shipment_id": "INTEGER",
            "compensation_error": "TEXT",
            "created_at": "TEXT",
            "updated_at": "TEXT",
        }
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Falta la columna '{col_name}' en 'orders'"
            assert col_type in columns[col_name], f"Tipo incorrecto para '{col_name}': {columns[col_name]}"

    def test_order_items_columns(self, temp_db):
        """Verifica las 7 columnas exactas de la tabla order_items según la spec §6."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(order_items);")
        columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
        conn.close()

        expected_columns = {
            "id": "INTEGER",
            "order_id": "INTEGER",
            "product_id": "INTEGER",
            "product_name": "TEXT",
            "unit_price": "REAL",
            "quantity": "INTEGER",
            "subtotal": "REAL",
        }
        for col_name, col_type in expected_columns.items():
            assert col_name in columns, f"Falta la columna '{col_name}' en 'order_items'"
            assert col_type in columns[col_name], f"Tipo incorrecto para '{col_name}': {columns[col_name]}"

    def test_init_db_idempotency(self, temp_db):
        """Llamar a init_db varias veces no genera error ni altera las tablas."""
        init_db(temp_db)
        init_db(temp_db)
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM orders;")
        assert cursor.fetchone()["c"] == 0
        conn.close()

    def test_database_starts_empty_without_seed(self, temp_db):
        """pedidos.db arranca vacía, sin registros semilla."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM orders;")
        assert cursor.fetchone()["c"] == 0
        cursor.execute("SELECT COUNT(*) AS c FROM order_items;")
        assert cursor.fetchone()["c"] == 0
        conn.close()

    def test_orders_status_check_constraint(self, temp_db):
        """Verifica que status solo permita 'PENDING', 'CONFIRMED', 'CANCELLED', 'FAILED'."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()

        # Inserción con estado no permitido debe fallar por CHECK constraint
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                cursor.execute(
                    """
                    INSERT INTO orders (customer_id, customer_name, coverage_zone, shipping_cost,
                                        total_amount, status, created_at, updated_at)
                    VALUES (1, 'Test', 'LOCAL', 50.0, 100.0, 'INVALID_STATUS', '2026-11-22T00:00:00', '2026-11-22T00:00:00');
                    """
                )
        conn.close()

    def test_foreign_key_constraint_enforced(self, temp_db):
        """Verifica que PRAGMA foreign_keys = ON impida insertar order_items con order_id inexistente."""
        conn = get_connection(temp_db)
        cursor = conn.cursor()

        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                cursor.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal)
                    VALUES (999, 1, 'Producto Fantasma', 50.0, 2, 100.0);
                    """
                )
        conn.close()


# ── T-16: Auth X-API-Key y GET /health ────────────────────────────────────────

class TestAuthAndHealth:
    def test_health_check_public_success(self, client):
        """GET /health es público y retorna HTTP 200 con JSON esperado (CF-1)."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "servicio-pedidos"
        assert data["version"] == "0.1.0"
        assert data["port"] == 8004

    def test_health_check_ignores_invalid_key(self, client):
        """GET /health no requiere autenticación incluso si se envía una clave inválida."""
        response = client.get("/health", headers={"X-API-Key": WRONG_KEY})
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_verify_api_key_direct_success(self):
        """verify_api_key retorna la clave si coincide con config.API_KEY."""
        res = verify_api_key(VALID_KEY)
        assert res == VALID_KEY

    def test_verify_api_key_direct_missing(self):
        """verify_api_key eleva HTTP 401 si la clave es None o vacía."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Clave de API inválida o ausente."
        assert exc_info.value.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_verify_api_key_direct_invalid(self):
        """verify_api_key eleva HTTP 401 si la clave es errónea."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(WRONG_KEY)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Clave de API inválida o ausente."
        assert exc_info.value.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_protected_route_rejects_missing_key(self, client):
        """Endpoint protegido responde HTTP 401 cuando falta el header X-API-Key (CF-2)."""
        response = client.get("/test-protected")
        assert response.status_code == 401
        assert response.json()["detail"] == "Clave de API inválida o ausente."
        assert response.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_protected_route_rejects_wrong_key(self, client):
        """Endpoint protegido responde HTTP 401 cuando la clave es incorrecta (CF-2)."""
        response = client.get("/test-protected", headers={"X-API-Key": WRONG_KEY})
        assert response.status_code == 401
        assert response.json()["detail"] == "Clave de API inválida o ausente."
        assert response.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_protected_route_accepts_valid_key(self, client):
        """Endpoint protegido responde HTTP 200 cuando se proporciona la clave válida."""
        response = client.get("/test-protected", headers={"X-API-Key": VALID_KEY})
        assert response.status_code == 200
        assert response.json()["message"] == "acceso permitido"
