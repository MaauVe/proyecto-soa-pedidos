"""
Tests consolidados para T-01, T-02, T-03 y T-04 (Bloque 1) — servicio-envios.
Cubre:
- T-01: Carga de configuración y paths (RNF-4, RNF-5, RNF-7).
- T-02: Esquema SQLite de shipments, DDL, tablas, índices y restricciones CHECK (RF-1, RNF-3).
- T-03: Autenticación X-API-Key y manejo de header ausente/inválido con 401 (RF-9).
- T-04: Endpoint público /health y metadatos de FastAPI (RF-2, RF-10).
"""
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

import config
from auth import verify_api_key
from database import get_connection, init_db
from main import app, health_check

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida-prueba"


# ── T-01: Configuración ────────────────────────────────────────────────────────

class TestConfig:
    def test_api_key_loaded_from_env(self):
        """API_KEY se carga desde el archivo .env raíz y coincide con el valor esperado."""
        assert config.API_KEY, "API_KEY no fue cargada desde .env"
        assert config.API_KEY == "changeme-local-key"

    def test_port_configuration(self):
        """El puerto configurado para servicio-envios es 8003."""
        assert config.PORT == 8003
        assert config.PORT_ENVIOS == 8003

    def test_db_path_within_service_dir(self):
        """envios.db reside dentro del directorio servicio-envios/."""
        assert config.DB_PATH.name == "envios.db"
        assert config.DB_PATH.parent == config.SERVICE_DIR
        assert config.SERVICE_DIR.name == "servicio-envios"

    def test_rates_configuration(self):
        """Las tarifas de las 3 zonas están configuradas con valores positivos."""
        assert config.RATE_LOCAL == 50.0
        assert config.RATE_REGIONAL == 100.0
        assert config.RATE_NACIONAL == 200.0

    def test_settings_object_exported(self):
        """El objeto settings puede importarse directamente como 'from config import settings'."""
        from config import settings
        assert settings.PORT_ENVIOS == 8003
        assert settings.RATE_LOCAL == 50.0
        assert settings.RATE_REGIONAL == 100.0
        assert settings.RATE_NACIONAL == 200.0


# ── T-02: Esquema de BD y modelo SQLite ───────────────────────────────────────

class TestDatabaseSchema:
    def test_init_db_creates_shipments_table(self, tmp_path):
        """init_db crea la tabla shipments correctamente."""
        db_file = tmp_path / "schema_test.db"
        init_db(db_file)
        conn = get_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='shipments';")
        row = cursor.fetchone()
        conn.close()
        assert row is not None, "La tabla 'shipments' no fue creada."

    def test_init_db_is_idempotent(self, tmp_path):
        """Llamar a init_db varias veces sucesivas no produce errores ni duplica nada."""
        db_file = tmp_path / "idempotent_test.db"
        init_db(db_file)
        init_db(db_file)
        conn = get_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shipments;")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_shipments_table_has_all_expected_columns(self, empty_db):
        """La tabla shipments tiene todas las columnas requeridas por la especificación."""
        conn = get_connection(empty_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(shipments);")
        columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
        conn.close()

        expected = [
            "id", "order_id", "zone", "recipient_name",
            "shipping_cost", "status", "created_at", "updated_at",
        ]
        for col in expected:
            assert col in columns, f"Falta la columna '{col}' en la tabla shipments"

    def test_check_constraint_zone(self, empty_db):
        """Zona no permitida debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (1, "INTERNACIONAL", "Juan Perez", 50.0, "PENDING", now, now),
                )
        conn.close()

    def test_check_constraint_status(self, empty_db):
        """Estado no permitido debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (2, "LOCAL", "Juan Perez", 50.0, "UNKNOWN_STATUS", now, now),
                )
        conn.close()

    def test_check_constraint_shipping_cost_non_negative(self, empty_db):
        """shipping_cost < 0 debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (3, "LOCAL", "Juan Perez", -10.0, "PENDING", now, now),
                )
        conn.close()

    def test_unique_constraint_order_id(self, empty_db):
        """order_id duplicado debe violar la restricción UNIQUE."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with conn:
            conn.execute(
                """
                INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (10, "LOCAL", "Cliente Uno", 50.0, "PENDING", now, now),
            )
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (10, "REGIONAL", "Cliente Dos", 100.0, "PENDING", now, now),
                )
        conn.close()


# ── T-03: Autenticación X-API-Key ─────────────────────────────────────────────

class TestAuth:
    def test_verify_api_key_none_raises_401(self):
        """Header ausente (None) lanza HTTPException 401 con WWW-Authenticate: X-API-Key."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        exc = exc_info.value
        assert exc.status_code == 401
        assert "API Key" in exc.detail
        assert exc.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_verify_api_key_empty_raises_401(self):
        """Header vacío lanza HTTPException 401 con WWW-Authenticate: X-API-Key."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("")
        exc = exc_info.value
        assert exc.status_code == 401
        assert exc.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_verify_api_key_wrong_raises_401(self):
        """Header con clave incorrecta lanza HTTPException 401 con WWW-Authenticate: X-API-Key."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(WRONG_KEY)
        exc = exc_info.value
        assert exc.status_code == 401
        assert exc.headers.get("WWW-Authenticate") == "X-API-Key"

    def test_verify_api_key_valid_passes(self):
        """Header con clave correcta retorna la clave sin lanzar excepciones."""
        result = verify_api_key(VALID_KEY)
        assert result == VALID_KEY


# ── T-04: /health y metadatos de la aplicación ────────────────────────────────

class TestHealthAndApp:
    def test_health_route_registered_as_get(self):
        """El endpoint /health está registrado como GET."""
        route = next((r for r in app.routes if getattr(r, "path", None) == "/health"), None)
        assert route is not None, "Ruta /health no registrada"
        assert "GET" in route.methods

    def test_health_does_not_require_api_key_dependency(self):
        """El endpoint /health no exige verify_api_key en sus dependencias."""
        route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
        deps = [d.dependency for d in getattr(route, "dependencies", [])]
        assert verify_api_key not in deps, "/health no debe exigir X-API-Key"

    def test_health_check_handler_response(self):
        """health_check() retorna el contrato esperado sin autenticación."""
        result = health_check()
        assert result["service"] == "servicio-envios"
        assert result["version"] == "0.1.0"
        assert result["status"] == "ok"
        assert result["port"] == 8003

    def test_fastapi_app_metadata(self):
        """La app FastAPI tiene configurados título, versión y documentación."""
        assert app.title == "Servicio de Envíos"
        assert app.version == "0.1.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"
