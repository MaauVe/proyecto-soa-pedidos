"""
Tests consolidados para T-11 a T-13 (Bloque 3) — servicio-inventario.
Cubre operaciones transaccionales y atómicas de stock:
- T-11: POST /products/reserve — Reserva atómica de stock (RF-8, RNF-9).
- T-12: POST /products/release — Liberación/restauración de stock (RF-9, RNF-9).
- T-13: POST /products/check-availability — Consulta sin descuento (RF-10).
"""
import sqlite3
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from auth import verify_api_key
from database import get_connection, init_db
from main import (
    app,
    check_availability,
    get_product,
    release_stock,
    reserve_stock,
)
from schemas import (
    CheckItem,
    CheckRequest,
    ReleaseItem,
    ReleaseRequest,
    ReserveItem,
    ReserveRequest,
)

DUMMY_KEY = "test-key"


def _route_requires_auth(path: str, method: str) -> bool:
    """Verifica si una ruta y método de FastAPI exigen la dependencia verify_api_key."""
    import inspect
    route = next((r for r in app.routes if getattr(r, "path", None) == path and method in getattr(r, "methods", [])), None)
    if not route:
        return False
    param_deps = [
        param.default.dependency
        for param in inspect.signature(route.endpoint).parameters.values()
        if hasattr(param.default, "dependency")
    ]
    dep_callables = [d.dependency for d in getattr(route, "dependencies", [])]
    return verify_api_key in (param_deps + dep_callables)


@pytest.fixture
def db_conn(tmp_path):
    """Crea una base de datos temporal con esquema y datos semilla cargados."""
    db_file = tmp_path / "test_stock.db"
    init_db(db_file)
    conn = get_connection(db_file)
    try:
        yield conn
    finally:
        conn.close()


# ── T-11: POST /products/reserve ───────────────────────────────────────────────

class TestReserveStock:
    def test_reserve_single_product_success(self, db_conn):
        """Reserva exitosa de un solo producto con stock suficiente."""
        # Producto 1 (LAPTOP-001) tiene stock inicial 20
        req = ReserveRequest(items=[ReserveItem(product_id=1, quantity=5)])
        res = reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)

        assert "reserved" in res
        assert len(res["reserved"]) == 1
        item = res["reserved"][0]
        assert item["product_id"] == 1
        assert item["name"] == "Laptop Ultradelgada 14\""
        assert item["unit_price"] == 12500.00
        assert item["weight_kg"] == 1.5
        assert item["quantity_reserved"] == 5
        assert item["stock_remaining"] == 15

        # Verificar persistencia en BD
        persisted = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert persisted["stock"] == 15

    def test_reserve_multiple_products_success(self, db_conn):
        """Reserva exitosa de múltiples productos con stock suficiente."""
        # Prod 1 (stock 20), Prod 2 (stock 150)
        req = ReserveRequest(items=[
            ReserveItem(product_id=1, quantity=3),
            ReserveItem(product_id=2, quantity=10),
        ])
        res = reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)
        assert len(res["reserved"]) == 2
        assert res["reserved"][0]["stock_remaining"] == 17
        assert res["reserved"][1]["stock_remaining"] == 140

    def test_reserve_exact_available_stock(self, db_conn):
        """Reservar exactamente todo el stock disponible deja stock_remaining en 0."""
        # Prod 4 (MONITOR-004) tiene stock 10
        req = ReserveRequest(items=[ReserveItem(product_id=4, quantity=10)])
        res = reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)
        assert res["reserved"][0]["stock_remaining"] == 0

        persisted = get_product(product_id=4, db=db_conn, _=DUMMY_KEY)
        assert persisted["stock"] == 0

    def test_reserve_insufficient_stock_rollback_total(self, db_conn):
        """Fallo por stock insuficiente hace rollback total: ningún producto se descuenta."""
        # Prod 1 tiene 20 (pide 5 -> ok), Prod 4 tiene 10 (pide 15 -> falla)
        req = ReserveRequest(items=[
            ReserveItem(product_id=1, quantity=5),
            ReserveItem(product_id=4, quantity=15),
        ])
        with pytest.raises(HTTPException) as exc_info:
            reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)

        assert exc_info.value.status_code == 409
        assert "insuficiente" in str(exc_info.value.detail).lower()

        # Verificar que Prod 1 NO fue descontado (rollback total)
        p1 = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        p4 = get_product(product_id=4, db=db_conn, _=DUMMY_KEY)
        assert p1["stock"] == 20
        assert p4["stock"] == 10

    def test_reserve_inactive_product_rollback_total(self, db_conn):
        """Producto inactivo en la lista provoca HTTP 409 y rollback total."""
        # Prod 5 (AURICULARES-005) es inactivo
        req = ReserveRequest(items=[
            ReserveItem(product_id=2, quantity=2),
            ReserveItem(product_id=5, quantity=1),
        ])
        with pytest.raises(HTTPException) as exc_info:
            reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)

        assert exc_info.value.status_code == 409
        assert "inactivo" in str(exc_info.value.detail).lower()

        # Prod 2 no debe haber cambiado
        p2 = get_product(product_id=2, db=db_conn, _=DUMMY_KEY)
        assert p2["stock"] == 150

    def test_reserve_non_existent_product_rollback_total(self, db_conn):
        """ID inexistente provoca HTTP 409 y rollback total."""
        req = ReserveRequest(items=[
            ReserveItem(product_id=1, quantity=1),
            ReserveItem(product_id=9999, quantity=1),
        ])
        with pytest.raises(HTTPException) as exc_info:
            reserve_stock(reserve_in=req, db=db_conn, _=DUMMY_KEY)

        assert exc_info.value.status_code == 409

        p1 = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert p1["stock"] == 20

    def test_reserve_duplicate_product_ids_validation_error(self):
        """Lista con product_id duplicados lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReserveRequest(items=[
                ReserveItem(product_id=1, quantity=2),
                ReserveItem(product_id=1, quantity=3),
            ])

    def test_reserve_empty_list_validation_error(self):
        """Lista vacía de items lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReserveRequest(items=[])

    def test_reserve_invalid_quantities_validation_error(self):
        """quantity <= 0 lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReserveItem(product_id=1, quantity=0)
        with pytest.raises(ValidationError):
            ReserveItem(product_id=1, quantity=-5)

    def test_route_registration_reserve(self):
        """Verifica que POST /products/reserve esté registrado con auth."""
        assert _route_requires_auth("/products/reserve", "POST")


# ── T-12: POST /products/release ───────────────────────────────────────────────

class TestReleaseStock:
    def test_release_stock_active_product(self, db_conn):
        """Liberar stock de un producto activo incrementa su stock."""
        # Prod 1 tiene 20
        req = ReleaseRequest(items=[ReleaseItem(product_id=1, quantity=5)])
        res = release_stock(release_in=req, db=db_conn, _=DUMMY_KEY)

        assert "released" in res
        assert len(res["released"]) == 1
        assert res["released"][0]["product_id"] == 1
        assert res["released"][0]["quantity_released"] == 5
        assert res["released"][0]["stock_after"] == 25

        persisted = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert persisted["stock"] == 25

    def test_release_stock_inactive_product_succeeds(self, db_conn):
        """Liberar stock sobre un producto INACTIVO es exitoso (inactividad no bloquea release)."""
        # Prod 5 (AURICULARES-005) es inactivo y tiene stock 0
        req = ReleaseRequest(items=[ReleaseItem(product_id=5, quantity=4)])
        res = release_stock(release_in=req, db=db_conn, _=DUMMY_KEY)

        assert res["released"][0]["product_id"] == 5
        assert res["released"][0]["stock_after"] == 4

        persisted = get_product(product_id=5, db=db_conn, _=DUMMY_KEY)
        assert persisted["stock"] == 4
        assert persisted["is_active"] is False  # Sigue inactivo

    def test_release_multiple_products(self, db_conn):
        """Liberar stock de múltiples productos incrementa todos."""
        req = ReleaseRequest(items=[
            ReleaseItem(product_id=1, quantity=2),
            ReleaseItem(product_id=2, quantity=10),
        ])
        res = release_stock(release_in=req, db=db_conn, _=DUMMY_KEY)
        assert len(res["released"]) == 2
        assert res["released"][0]["stock_after"] == 22
        assert res["released"][1]["stock_after"] == 160

    def test_release_non_existing_product_raises_404(self, db_conn):
        """Si un producto en la lista no existe, lanza HTTP 404 y ningún stock se altera."""
        req = ReleaseRequest(items=[
            ReleaseItem(product_id=1, quantity=5),
            ReleaseItem(product_id=9999, quantity=2),
        ])
        with pytest.raises(HTTPException) as exc_info:
            release_stock(release_in=req, db=db_conn, _=DUMMY_KEY)

        assert exc_info.value.status_code == 404

        # Prod 1 no debe haber cambiado
        p1 = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert p1["stock"] == 20

    def test_release_duplicate_product_ids_validation_error(self):
        """Lista con product_id duplicados lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReleaseRequest(items=[
                ReleaseItem(product_id=1, quantity=2),
                ReleaseItem(product_id=1, quantity=3),
            ])

    def test_release_empty_list_validation_error(self):
        """Lista vacía lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReleaseRequest(items=[])

    def test_release_invalid_quantities_validation_error(self):
        """quantity <= 0 lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            ReleaseItem(product_id=1, quantity=0)

    def test_route_registration_release(self):
        """Verifica que POST /products/release esté registrado con auth."""
        assert _route_requires_auth("/products/release", "POST")


# ── T-13: POST /products/check-availability ────────────────────────────────────

class TestCheckAvailability:
    def test_check_all_available_success(self, db_conn):
        """Todos disponibles retorna all_available=True con metadatos por producto."""
        req = CheckRequest(items=[
            CheckItem(product_id=1, quantity=5),
            CheckItem(product_id=2, quantity=20),
        ])
        res = check_availability(check_in=req, db=db_conn, _=DUMMY_KEY)

        assert res["all_available"] is True
        assert len(res["results"]) == 2
        r1 = res["results"][0]
        assert r1["product_id"] == 1
        assert r1["name"] == "Laptop Ultradelgada 14\""
        assert r1["unit_price"] == 12500.00
        assert r1["weight_kg"] == 1.5
        assert r1["available"] is True
        assert r1["stock_current"] == 20
        assert r1["quantity_requested"] == 5
        assert r1["reason"] is None

    def test_check_stock_not_modified(self, db_conn):
        """La verificación de disponibilidad NO modifica el stock."""
        req = CheckRequest(items=[CheckItem(product_id=1, quantity=5)])
        check_availability(check_in=req, db=db_conn, _=DUMMY_KEY)

        persisted = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert persisted["stock"] == 20

    def test_check_insufficient_stock_returns_false(self, db_conn):
        """Stock insuficiente retorna all_available=False y motivo en el resultado."""
        # Prod 4 tiene 10, pide 12
        req = CheckRequest(items=[
            CheckItem(product_id=1, quantity=2),
            CheckItem(product_id=4, quantity=12),
        ])
        res = check_availability(check_in=req, db=db_conn, _=DUMMY_KEY)

        assert res["all_available"] is False
        assert res["results"][0]["available"] is True
        assert res["results"][1]["available"] is False
        assert "insuficiente" in res["results"][1]["reason"].lower()

    def test_check_inactive_product_returns_false(self, db_conn):
        """Producto inactivo retorna available=False con motivo explicativo."""
        # Prod 5 es inactivo
        req = CheckRequest(items=[CheckItem(product_id=5, quantity=1)])
        res = check_availability(check_in=req, db=db_conn, _=DUMMY_KEY)

        assert res["all_available"] is False
        assert res["results"][0]["available"] is False
        assert "inactivo" in res["results"][0]["reason"].lower()

    def test_check_non_existent_product_returns_false(self, db_conn):
        """Producto inexistente retorna available=False con motivo explicativo."""
        req = CheckRequest(items=[CheckItem(product_id=9999, quantity=1)])
        res = check_availability(check_in=req, db=db_conn, _=DUMMY_KEY)

        assert res["all_available"] is False
        assert res["results"][0]["available"] is False
        assert "no encontrado" in res["results"][0]["reason"].lower()

    def test_check_duplicate_product_ids_validation_error(self):
        """Lista con IDs duplicados lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            CheckRequest(items=[
                CheckItem(product_id=1, quantity=1),
                CheckItem(product_id=1, quantity=2),
            ])

    def test_check_empty_list_validation_error(self):
        """Lista vacía lanza ValidationError (HTTP 422)."""
        with pytest.raises(ValidationError):
            CheckRequest(items=[])

    def test_route_registration_check_availability(self):
        """Verifica que POST /products/check-availability esté registrado con auth."""
        assert _route_requires_auth("/products/check-availability", "POST")
