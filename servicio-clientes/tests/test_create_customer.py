"""
Tests T-04: Creación de cliente - POST /customers (RF-2).
Pruebas de esquemas Pydantic, lógica de creación en BD y registro de ruta en FastAPI.
"""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, create_customer
from models import Base, Customer
from schemas import CustomerCreate, CustomerResponse


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


# ── Pruebas de validación de esquema Pydantic (HTTP 422) ──────────────────────

class TestCustomerCreateSchema:
    def test_valid_data_creates_schema_instance(self):
        """Datos válidos crean una instancia de CustomerCreate."""
        data = {
            "full_name": "Juan Pérez",
            "email": "juan.perez@example.com",
            "phone": "555-1234",
            "delivery_address": "Av. Reforma 123",
            "coverage_zone": "Local",
        }
        customer = CustomerCreate(**data)
        assert customer.full_name == "Juan Pérez"
        assert customer.email == "juan.perez@example.com"

    def test_missing_required_fields_raises_validation_error(self):
        """Falta de campos obligatorios lanza ValidationError."""
        with pytest.raises(ValidationError):
            CustomerCreate(full_name="Solo Nombre")

    def test_email_without_at_symbol_raises_validation_error(self):
        """Correo sin '@' lanza ValidationError."""
        with pytest.raises(ValidationError):
            CustomerCreate(
                full_name="Test User",
                email="correo_invalido.com",
                phone="123456",
                delivery_address="Calle 1",
                coverage_zone="Local",
            )

    def test_blank_fields_raise_validation_error(self):
        """Campos vacíos o con solo espacios lanzan ValidationError."""
        with pytest.raises(ValidationError):
            CustomerCreate(
                full_name="   ",
                email="valido@example.com",
                phone="123456",
                delivery_address="Calle 1",
                coverage_zone="Local",
            )


# ── Pruebas del endpoint / lógica de creación (HTTP 201 & 409) ────────────────

class TestCreateCustomerEndpoint:
    def test_create_customer_success_returns_201_data(self, db_session):
        """Creación exitosa persiste el cliente y retorna todos sus campos."""
        payload = CustomerCreate(
            full_name="Laura Gómez",
            email="laura.gomez@example.com",
            phone="5559876543",
            delivery_address="Calle Pino 45, Col. Bosques",
            coverage_zone="Local",
        )

        res = create_customer(customer_in=payload, db=db_session, _="mock_key")
        assert res.id is not None
        assert res.full_name == payload.full_name
        assert res.email == payload.email
        assert res.phone == payload.phone
        assert res.delivery_address == payload.delivery_address
        assert res.coverage_zone == payload.coverage_zone
        assert res.is_active is True
        assert res.created_at is not None
        assert res.updated_at is not None

        # Verificar que efectivamente está en la base de datos
        db_customer = db_session.query(Customer).filter(Customer.id == res.id).first()
        assert db_customer is not None
        assert db_customer.email == "laura.gomez@example.com"

    def test_create_customer_duplicate_email_raises_409(self, db_session):
        """Intentar registrar un correo existente retorna HTTP 409 en español."""
        payload = CustomerCreate(
            full_name="Cliente Uno",
            email="repetido@example.com",
            phone="111111",
            delivery_address="Dir 1",
            coverage_zone="Local",
        )
        create_customer(customer_in=payload, db=db_session, _="mock_key")

        payload_duplicate = CustomerCreate(
            full_name="Cliente Dos",
            email="repetido@example.com",
            phone="222222",
            delivery_address="Dir 2",
            coverage_zone="Regional",
        )

        with pytest.raises(HTTPException) as exc_info:
            create_customer(customer_in=payload_duplicate, db=db_session, _="mock_key")

        assert exc_info.value.status_code == 409
        assert "Ya existe un cliente registrado con ese correo electrónico." in exc_info.value.detail

    def test_create_customer_duplicate_email_case_insensitive_raises_409(self, db_session):
        """Validación de correo duplicado es insensible a mayúsculas y minúsculas."""
        payload = CustomerCreate(
            full_name="Mayúsculas User",
            email="MixCase@Example.Com",
            phone="333333",
            delivery_address="Dir 3",
            coverage_zone="Nacional",
        )
        create_customer(customer_in=payload, db=db_session, _="mock_key")

        payload_lower = CustomerCreate(
            full_name="Minúsculas User",
            email="mixcase@example.com",
            phone="444444",
            delivery_address="Dir 4",
            coverage_zone="Local",
        )

        with pytest.raises(HTTPException) as exc_info:
            create_customer(customer_in=payload_lower, db=db_session, _="mock_key")

        assert exc_info.value.status_code == 409
        assert "Ya existe un cliente registrado con ese correo electrónico." in exc_info.value.detail


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestCreateCustomerRouteMetadata:
    def test_post_customers_route_registered(self):
        """La ruta POST /customers está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "POST" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta POST /customers no registrada"

    def test_post_customers_status_code_is_201(self):
        """El endpoint POST /customers tiene status_code configurado en 201."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "POST" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 201

    def test_post_customers_requires_api_key(self):
        """La ruta POST /customers incluye la dependencia de autenticación verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "POST" in getattr(r, "methods", [])
            ),
            None,
        )
        dep_callables = [d.dependency for d in getattr(route, "dependencies", [])]
        # También puede estar en los parámetros de la función del endpoint
        import inspect
        param_deps = [
            param.default.dependency
            for param in inspect.signature(route.endpoint).parameters.values()
            if hasattr(param.default, "dependency")
        ]
        all_deps = dep_callables + param_deps
        assert verify_api_key in all_deps, "POST /customers debe requerir verify_api_key"
