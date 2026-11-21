"""
Tests T-08: Desactivación lógica de cliente - DELETE /customers/{customer_id} (RF-6).
Pruebas de borrado lógico (is_active=False), idempotencia/conflicto 409, 404 y permanencia en base de datos.
"""
import time
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, deactivate_customer, get_customer
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


# ── Pruebas del endpoint deactivate_customer ──────────────────────────────────

class TestDeactivateCustomerEndpoint:
    def test_deactivate_active_customer_success(self, db_session):
        """Desactivar un cliente activo cambia is_active a False y retorna HTTP 200."""
        customer = Customer(
            full_name="Cliente a Desactivar",
            email="desactivar@example.com",
            phone="123456",
            delivery_address="Calle Desactiva 1",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        original_updated_at = customer.updated_at

        time.sleep(0.01)

        res = deactivate_customer(
            customer_id=customer.id,
            db=db_session,
            _="mock_key",
        )

        assert res.id == customer.id
        assert res.is_active is False
        assert res.updated_at >= original_updated_at

        # Verificar en base de datos que sigue existiendo
        db_cust = db_session.query(Customer).filter(Customer.id == customer.id).first()
        assert db_cust is not None
        assert db_cust.is_active is False

    def test_deactivated_customer_still_retrievable_via_get(self, db_session):
        """Un cliente desactivado sigue siendo consultable vía GET /customers/{id} (CF-6)."""
        customer = Customer(
            full_name="Cliente Consulta",
            email="consulta@example.com",
            phone="555000",
            delivery_address="Av. Siempre Viva 742",
            coverage_zone="Regional",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Desactivamos el cliente
        deactivate_customer(customer_id=customer.id, db=db_session, _="mock_key")

        # Consultamos vía get_customer
        res_get = get_customer(customer_id=customer.id, db=db_session, _="mock_key")
        assert res_get.id == customer.id
        assert res_get.is_active is False
        assert res_get.email == "consulta@example.com"

    def test_deactivate_already_inactive_customer_raises_409(self, db_session):
        """Intentar desactivar un cliente que ya está inactivo retorna HTTP 409."""
        customer = Customer(
            full_name="Cliente Ya Inactivo",
            email="inactivo_previo@example.com",
            phone="777888",
            delivery_address="Calle Inactiva 2",
            coverage_zone="Local",
            is_active=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with pytest.raises(HTTPException) as exc_info:
            deactivate_customer(
                customer_id=customer.id,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "El cliente ya se encuentra inactivo."

    def test_deactivate_non_existent_customer_raises_404(self, db_session):
        """Intentar desactivar un ID que no existe retorna HTTP 404 'Cliente no encontrado.'."""
        with pytest.raises(HTTPException) as exc_info:
            deactivate_customer(
                customer_id=9999,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Cliente no encontrado."


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestDeactivateCustomerRouteMetadata:
    def test_delete_customer_route_registered(self):
        """La ruta DELETE /customers/{customer_id} está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "DELETE" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta DELETE /customers/{customer_id} no registrada"

    def test_delete_customer_status_code_is_200(self):
        """El endpoint DELETE /customers/{customer_id} tiene status_code 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "DELETE" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_delete_customer_requires_api_key(self):
        """La ruta DELETE /customers/{customer_id} incluye verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "DELETE" in getattr(r, "methods", [])
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
        assert verify_api_key in all_deps, "DELETE /customers/{customer_id} debe requerir verify_api_key"

    def test_delete_customer_response_model_is_customer_response(self):
        """El response_model es CustomerResponse."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "DELETE" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.response_model == CustomerResponse
