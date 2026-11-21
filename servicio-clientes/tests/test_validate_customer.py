"""
Tests T-10: Endpoint de validación semántica - GET /customers/{customer_id}/validate (RF-8).
Pruebas de validación para orquestador (HTTP 200 activo, 404 inexistente, 409 inactivo y metadatos).
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, validate_customer
from models import Base, Customer
from schemas import CustomerValidateResponse


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


# ── Pruebas del endpoint validate_customer ────────────────────────────────────

class TestValidateCustomerEndpoint:
    def test_validate_existing_active_customer_returns_200_and_payload(self, db_session):
        """Cliente existente y activo retorna HTTP 200 con id, full_name, coverage_zone, delivery_address e is_active."""
        customer = Customer(
            full_name="Valid Active Customer",
            email="active@example.com",
            phone="1234567890",
            delivery_address="Calle Mayor 100",
            coverage_zone="Nacional",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        res = validate_customer(
            customer_id=customer.id,
            db=db_session,
            _="mock_key",
        )

        assert res.id == customer.id
        assert res.full_name == "Valid Active Customer"
        assert res.coverage_zone == "Nacional"
        assert res.delivery_address == "Calle Mayor 100"
        assert res.is_active is True

    def test_validate_non_existent_customer_raises_404(self, db_session):
        """Si el cliente no existe, retorna HTTP 404 'Cliente no encontrado.'."""
        with pytest.raises(HTTPException) as exc_info:
            validate_customer(
                customer_id=7777,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Cliente no encontrado."

    def test_validate_existing_inactive_customer_raises_409(self, db_session):
        """Si el cliente existe pero está inactivo, retorna HTTP 409 'El cliente existe pero se encuentra inactivo.'."""
        customer = Customer(
            full_name="Valid Inactive Customer",
            email="inactive@example.com",
            phone="555444333",
            delivery_address="Av. Desolación 404",
            coverage_zone="Local",
            is_active=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with pytest.raises(HTTPException) as exc_info:
            validate_customer(
                customer_id=customer.id,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "El cliente existe pero se encuentra inactivo."


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestValidateCustomerRouteMetadata:
    def test_validate_customer_route_registered(self):
        """La ruta GET /customers/{customer_id}/validate está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/validate"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta GET /customers/{customer_id}/validate no registrada"

    def test_validate_customer_status_code_is_200(self):
        """El endpoint GET /customers/{customer_id}/validate tiene status_code 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/validate"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_validate_customer_requires_api_key(self):
        """La ruta GET /customers/{customer_id}/validate incluye verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/validate"
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
        assert verify_api_key in all_deps, (
            "GET /customers/{customer_id}/validate debe requerir verify_api_key"
        )

    def test_validate_customer_response_model_is_customer_validate_response(self):
        """El response_model es CustomerValidateResponse."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/validate"
                and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.response_model == CustomerValidateResponse
