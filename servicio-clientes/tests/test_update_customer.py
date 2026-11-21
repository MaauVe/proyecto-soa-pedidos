"""
Tests T-07: Actualización parcial de cliente - PATCH /customers/{customer_id} (RF-5).
Pruebas de actualización de campos, no-op en cuerpo vacío, duplicación de email, 404 y metadatos de ruta.
"""
import time
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, update_customer
from models import Base, Customer
from schemas import CustomerResponse, CustomerUpdate


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


# ── Pruebas de esquemas Pydantic ──────────────────────────────────────────────

class TestCustomerUpdateSchema:
    def test_empty_update_schema_is_valid(self):
        """CustomerUpdate sin campos es válido (todos None)."""
        update_schema = CustomerUpdate()
        assert update_schema.model_dump(exclude_unset=True) == {}

    def test_invalid_email_format_raises_validation_error(self):
        """Correo sin '@' en CustomerUpdate lanza ValidationError."""
        with pytest.raises(ValidationError):
            CustomerUpdate(email="invalido.com")

    def test_blank_field_raises_validation_error(self):
        """Campos vacíos o con espacios en CustomerUpdate lanzan ValidationError."""
        with pytest.raises(ValidationError):
            CustomerUpdate(phone="   ")


# ── Pruebas del endpoint update_customer ──────────────────────────────────────

class TestUpdateCustomerEndpoint:
    def test_partial_update_single_field_success(self, db_session):
        """Actualizar un solo campo modifica únicamente ese campo y preserva el resto."""
        customer = Customer(
            full_name="Original Name",
            email="original@example.com",
            phone="111-222-333",
            delivery_address="Calle Original 10",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        update_payload = CustomerUpdate(phone="999-888-777")
        res = update_customer(
            customer_id=customer.id,
            customer_in=update_payload,
            db=db_session,
            _="mock_key",
        )

        assert res.id == customer.id
        assert res.phone == "999-888-777"
        assert res.full_name == "Original Name"
        assert res.email == "original@example.com"
        assert res.delivery_address == "Calle Original 10"
        assert res.coverage_zone == "Local"

    def test_empty_payload_is_noop(self, db_session):
        """Enviar un cuerpo vacío no modifica los campos del cliente."""
        customer = Customer(
            full_name="No Op User",
            email="noop@example.com",
            phone="123456",
            delivery_address="Calle 0",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        update_payload = CustomerUpdate()
        res = update_customer(
            customer_id=customer.id,
            customer_in=update_payload,
            db=db_session,
            _="mock_key",
        )

        assert res.id == customer.id
        assert res.full_name == "No Op User"
        assert res.email == "noop@example.com"

    def test_update_email_to_existing_another_customer_raises_409(self, db_session):
        """Cambiar email al de otro cliente lanza HTTP 409 (case-insensitive)."""
        c1 = Customer(
            full_name="User 1",
            email="user1@example.com",
            phone="111",
            delivery_address="Dir 1",
            coverage_zone="Local",
            is_active=True,
        )
        c2 = Customer(
            full_name="User 2",
            email="user2@example.com",
            phone="222",
            delivery_address="Dir 2",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add_all([c1, c2])
        db_session.commit()
        db_session.refresh(c2)

        # Intentar cambiar email de c2 al de c1 (en mayúsculas)
        update_payload = CustomerUpdate(email="USER1@EXAMPLE.COM")
        with pytest.raises(HTTPException) as exc_info:
            update_customer(
                customer_id=c2.id,
                customer_in=update_payload,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 409
        assert "Ya existe un cliente registrado con ese correo electrónico." in exc_info.value.detail

    def test_update_email_to_same_email_success(self, db_session):
        """Actualizar enviando el mismo correo del propio cliente no colisiona consigo mismo."""
        customer = Customer(
            full_name="Same Email",
            email="same@example.com",
            phone="123",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        update_payload = CustomerUpdate(email="same@example.com", full_name="Updated Name")
        res = update_customer(
            customer_id=customer.id,
            customer_in=update_payload,
            db=db_session,
            _="mock_key",
        )
        assert res.full_name == "Updated Name"
        assert res.email == "same@example.com"

    def test_update_non_existent_customer_raises_404(self, db_session):
        """Intentar actualizar un ID inexistente lanza HTTP 404 'Cliente no encontrado.'."""
        update_payload = CustomerUpdate(full_name="Ghost")
        with pytest.raises(HTTPException) as exc_info:
            update_customer(
                customer_id=8888,
                customer_in=update_payload,
                db=db_session,
                _="mock_key",
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Cliente no encontrado."

    def test_updated_at_changes_after_update(self, db_session):
        """El campo updated_at cambia al realizar una modificación exitosa."""
        customer = Customer(
            full_name="Time Test",
            email="time@example.com",
            phone="111",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=True,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)
        original_updated_at = customer.updated_at

        time.sleep(0.01)

        update_payload = CustomerUpdate(full_name="Time Test Modified")
        res = update_customer(
            customer_id=customer.id,
            customer_in=update_payload,
            db=db_session,
            _="mock_key",
        )
        assert res.updated_at >= original_updated_at


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestUpdateCustomerRouteMetadata:
    def test_patch_customer_route_registered(self):
        """La ruta PATCH /customers/{customer_id} está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta PATCH /customers/{customer_id} no registrada"

    def test_patch_customer_status_code_is_200(self):
        """El endpoint PATCH /customers/{customer_id} tiene status_code 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_patch_customer_requires_api_key(self):
        """La ruta PATCH /customers/{customer_id} incluye la dependencia verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
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
        assert verify_api_key in all_deps, "PATCH /customers/{customer_id} debe requerir verify_api_key"

    def test_patch_customer_response_model_is_customer_response(self):
        """El response_model de PATCH /customers/{customer_id} es CustomerResponse."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers/{customer_id}"
                and "PATCH" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.response_model == CustomerResponse
