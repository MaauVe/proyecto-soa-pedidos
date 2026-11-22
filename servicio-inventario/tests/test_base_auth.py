"""
Tests consolidados para T-01, T-02, T-03 y T-04 (Bloque 1) — servicio-inventario.
Cubre:
- T-01: Carga de configuración y paths (RNF-2, RNF-6, RNF-8).
- T-02: Esquema SQLite, DDL, tablas, índices y restricciones CHECK (RF-1, RNF-6).
- T-03: Carga de datos semilla e idempotencia (RF-1).
- T-04: Autenticación X-API-Key y endpoint público /health (RF-11, RF-12).
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
from seed import seed_products

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida-prueba"


# ── T-01: Configuración ────────────────────────────────────────────────────────

class TestConfig:
    def test_api_key_loaded_from_env(self):
        """API_KEY se carga desde el archivo .env raíz y no está vacía."""
        assert config.API_KEY, "API_KEY no fue cargada desde .env"
        assert config.API_KEY == "changeme-local-key"

    def test_port_configuration(self):
        """El puerto configurado para servicio-inventario es 8002."""
        assert config.PORT == 8002

    def test_db_path_within_service_dir(self):
        """inventario.db reside dentro del directorio servicio-inventario/."""
        assert config.DB_PATH.name == "inventario.db"
        assert config.DB_PATH.parent == config.SERVICE_DIR
        assert config.SERVICE_DIR.name == "servicio-inventario"


# ── T-02: Esquema de BD y modelo SQLite ───────────────────────────────────────

class TestDatabaseSchema:
    def test_init_db_creates_products_table(self, tmp_path):
        """init_db crea la tabla products correctamente."""
        db_file = tmp_path / "schema_test.db"
        init_db(db_file)
        conn = get_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products';")
        row = cursor.fetchone()
        conn.close()
        assert row is not None, "La tabla 'products' no fue creada."

    def test_init_db_is_idempotent(self, tmp_path):
        """Llamar a init_db varias veces sucesivas no produce errores."""
        db_file = tmp_path / "idempotent_test.db"
        init_db(db_file)
        init_db(db_file)
        conn = get_connection(db_file)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products;")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 5, "init_db ejecutado dos veces no debe duplicar registros semilla."

    def test_products_table_has_all_expected_columns(self, empty_db):
        """La tabla products tiene todas las columnas requeridas por la especificación."""
        conn = get_connection(empty_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(products);")
        columns = {row["name"]: row["type"].upper() for row in cursor.fetchall()}
        conn.close()

        expected = [
            "id", "sku", "name", "description", "unit_price",
            "weight_kg", "stock", "is_active", "created_at", "updated_at",
        ]
        for col in expected:
            assert col in columns, f"Falta la columna '{col}' en la tabla products"

    def test_check_constraint_unit_price_positive(self, empty_db):
        """unit_price <= 0 debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("PROD-ERR1", "Invalido", 0.0, 1.0, 10, 1, now, now),
                )
        conn.close()

    def test_check_constraint_weight_positive(self, empty_db):
        """weight_kg <= 0 debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("PROD-ERR2", "Invalido", 100.0, 0.0, 10, 1, now, now),
                )
        conn.close()

    def test_check_constraint_stock_non_negative(self, empty_db):
        """stock < 0 debe violar la restricción CHECK."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("PROD-ERR3", "Invalido", 100.0, 1.0, -1, 1, now, now),
                )
        conn.close()

    def test_unique_constraint_sku(self, empty_db):
        """SKU duplicado debe violar la restricción UNIQUE."""
        conn = get_connection(empty_db)
        now = datetime.now(UTC).isoformat()
        with conn:
            conn.execute(
                """
                INSERT INTO products (sku, name, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                ("SKU-DUP", "Prod 1", 100.0, 1.0, 5, 1, now, now),
            )
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute(
                    """
                    INSERT INTO products (sku, name, unit_price, weight_kg, stock, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    ("SKU-DUP", "Prod 2", 200.0, 2.0, 10, 1, now, now),
                )
        conn.close()


# ── T-03: Seed de datos iniciales ─────────────────────────────────────────────

class TestSeed:
    def test_seed_inserts_exact_count(self, empty_db):
        """seed_products inserta exactamente 5 productos en BD vacía."""
        conn = get_connection(empty_db)
        inserted = seed_products(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products;")
        total = cursor.fetchone()[0]
        conn.close()
        assert inserted == 5
        assert total == 5

    def test_seed_is_skipped_if_table_not_empty(self, seeded_db):
        """seed_products no inserta nada si ya existen productos."""
        conn = get_connection(seeded_db)
        inserted = seed_products(conn)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products;")
        total = cursor.fetchone()[0]
        conn.close()
        assert inserted == 0
        assert total == 5

    def test_seed_contains_inactive_product_with_zero_stock(self, seeded_db):
        """El seed incluye al menos un producto inactivo con stock 0."""
        conn = get_connection(seeded_db)
        cursor = conn.cursor()
        cursor.execute("SELECT sku, stock, is_active FROM products WHERE is_active = 0;")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) >= 1
        inactive = rows[0]
        assert inactive["stock"] == 0

    def test_seed_fields_validity(self, seeded_db):
        """Todos los productos semilla tienen valores válidos para sus atributos clave."""
        conn = get_connection(seeded_db)
        cursor = conn.cursor()
        cursor.execute("SELECT sku, name, unit_price, weight_kg, stock, is_active FROM products;")
        rows = cursor.fetchall()
        conn.close()
        assert len(rows) == 5
        for row in rows:
            assert row["sku"]
            assert row["name"]
            assert row["unit_price"] > 0
            assert row["weight_kg"] > 0
            assert row["stock"] >= 0


# ── T-04: Autenticación y /health ─────────────────────────────────────────────

class TestAuthAndHealth:
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
        assert result["service"] == "servicio-inventario"
        assert result["version"] == "0.1.0"
        assert result["status"] == "ok"
        assert result["port"] == 8002

    def test_fastapi_app_metadata(self):
        """La app FastAPI tiene configurados título, versión y documentación."""
        assert app.title == "Servicio de Catálogo e Inventario"
        assert app.version == "0.1.0"
        assert app.docs_url == "/docs"
        assert app.redoc_url == "/redoc"

    def test_verify_api_key_none_raises_401(self):
        """Header ausente (None) lanza HTTPException 401 en español con header WWW-Authenticate."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        exc = exc_info.value
        assert exc.status_code == 401
        assert "API Key" in exc.detail
        assert "WWW-Authenticate" in exc.headers

    def test_verify_api_key_empty_raises_401(self):
        """Header vacío lanza HTTPException 401."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("")
        assert exc_info.value.status_code == 401

    def test_verify_api_key_wrong_raises_401(self):
        """Header con clave incorrecta lanza HTTPException 401."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(WRONG_KEY)
        assert exc_info.value.status_code == 401

    def test_verify_api_key_valid_passes(self):
        """Header con clave correcta retorna la clave y no lanza excepciones."""
        result = verify_api_key(VALID_KEY)
        assert result == VALID_KEY
