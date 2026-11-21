"""
Tests T-09: Reactivación de cliente - PATCH /customers/{customer_id}/reactivate (RF-7).
Pruebas de reactivación (is_active=True), conflicto 409 en clientes ya activos, 404 y metadatos de ruta.
"""
import time
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, reactivate_customer
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


# ── Pruebas del endpoint reactivate_customer ──────────────────────────────────

class TestReactivateCustomerEndpoint:
    def test_reactivate_inactive_customer_success(self, db_session):
        """Reactivar un cliente inactivo establece is_active=True y retorna HTTP 200."""
        customer = Customer(
            full_name="Cliente Inactivo Para Reactivar",
            email="reactivar@example.com",
            phone="123456",
            delivery_address="Calle Reactivación 10",
            coverage_zone="Local",
            is_active=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        original_updated_at = customer.updated_at

        time.sleep(0.01)

        res = reactivate_customer(
            customer_id=customer.id,
            db=db_session,
            _="mock_key",
        )

        assert res.id == customer.id
        assert res.is_active is True
        assert res.updated_at >= original_updated_at

        # Verificar en base de datos
        db_cust = db_session.query(Customer).filter(Customer.id == customer.id).first()
        assert db_cust is not None
        assert db_cust.is_active is True

    def test_reactivate_already_active_customer_raises_409(self, db_session):
        """Intentar reactivar un cliente que ya se encuentra activo retorna HTTP 409."""
        customer = Customer(
            full_name="Cliente Ya Activo",
            email="activo_previo@example.com",
            phone="987654",
            delivery_address="Av. Activa 12",
            coverage_zone="Nacional",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with pytest.raises(HTTPException) as exc_info:
            reactivate_customer(
                customer_id=customer.id,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "El cliente ya se encuentra activo."

    def test_reactivate_non_existent_customer_raises_404(self, db_session):
        """Intentar reactivar un ID no existente retorna HTTP 404 'Cliente no encontrado.'."""
        with pytest.raises(HTTPException) as exc_info:
            reactivate_customer(
                customer_id=9999,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Cliente no encontrado."


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestReactivateCustomerRouteMetadata:
    def test_reactivate_customer_route_registered(self):
        """La ruta PATCH /customers/{customer_id}/reactivate está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/reactivate"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta PATCH /customers/{customer_id}/reactivate no registrada"

    def test_reactivate_customer_status_code_is_200(self):
        """El endpoint PATCH /customers/{customer_id}/reactivate tiene status_code 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/reactivate"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_reactivate_customer_requires_api_key(self):
        """La ruta PATCH /customers/{customer_id}/reactivate incluye verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/reactivate"
                and "PATCH" in getattr(r, "methods", [])
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
            "PATCH /customers/{customer_id}/reactivate debe requerir verify_api_key"
        )

    def test_reactivate_customer_response_model_is_customer_response(self):
        """El response_model es CustomerResponse."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}/reactivate"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.response_model == CustomerResponse
