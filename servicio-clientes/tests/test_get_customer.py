"""
Tests T-05: Consulta por ID - GET /customers/{customer_id} (RF-3).
Pruebas de consulta de clientes activos, inactivos, inexistentes y metadatos de ruta.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, get_customer
from models import Base, Customer
from schemas import CustomerResponse


# ── Fixture: Sesión SQLite en memoria ──────────────────────────────────────────

@pytest.fixture
def db_session():
    """Sesión SQLite aislada en memoria."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Pruebas del endpoint get_customer ─────────────────────────────────────────

class TestGetCustomerEndpoint:
    def test_get_existing_active_customer_returns_200(self, db_session):
        """Consultar un cliente existente y activo retorna HTTP 200 y sus datos completos."""
        customer = Customer(
            full_name="Mario Bros",
            email="mario@nintendo.com",
            phone="555-123-456",
            delivery_address="Mushroom Kingdom 1",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        res = get_customer(customer_id=customer.id, db=db_session, _="mock_key")
        assert res.id == customer.id
        assert res.full_name == "Mario Bros"
        assert res.email == "mario@nintendo.com"
        assert res.phone == "555-123-456"
        assert res.delivery_address == "Mushroom Kingdom 1"
        assert res.coverage_zone == "Local"
        assert res.is_active is True
        assert res.created_at is not None
        assert res.updated_at is not None

    def test_get_existing_inactive_customer_returns_200(self, db_session):
        """Consultar un cliente inactivo también retorna HTTP 200 con is_active=False."""
        customer = Customer(
            full_name="Luigi Bros",
            email="luigi@nintendo.com",
            phone="555-654-321",
            delivery_address="Mushroom Kingdom 2",
            coverage_zone="Regional",
            is_active=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        res = get_customer(customer_id=customer.id, db=db_session, _="mock_key")
        assert res.id == customer.id
        assert res.is_active is False
        assert res.full_name == "Luigi Bros"

    def test_get_non_existent_customer_raises_404(self, db_session):
        """Consultar un ID que no existe lanza HTTP 404 con mensaje 'Cliente no encontrado.'."""
        with pytest.raises(HTTPException) as exc_info:
            get_customer(customer_id=9999, db=db_session, _="mock_key")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Cliente no encontrado."


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestGetCustomerRouteMetadata:
    def test_get_customer_route_registered(self):
        """La ruta GET /customers/{customer_id} está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta GET /customers/{customer_id} no registrada"

    def test_get_customer_status_code_is_200(self):
        """El endpoint GET /customers/{customer_id} tiene status_code 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_get_customer_requires_api_key(self):
        """La ruta GET /customers/{customer_id} incluye la dependencia verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        import inspect
        param_deps = [
            param.default.dependency
            for param in inspect.signature(route.endpoint).parameters.values()
            if hasattr(param.default, "dependency")
        ]
        dep_callables = [d.dependency for d in getattr(route, "dependencies", [])]
        all_deps = dep_callables + param_deps
        assert verify_api_key in all_deps, "GET /customers/{customer_id} debe requerir verify_api_key"

    def test_get_customer_id_param_is_int(self):
        """El parámetro customer_id está tipado como entero para validación automática."""
        import inspect
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        sig = inspect.signature(route.endpoint)
        assert sig.parameters["customer_id"].annotation is int
