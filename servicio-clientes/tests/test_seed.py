"""
Tests T-02: Modelo de datos, BD y seed automático (RF-1).
Verifica que el esquema se crea correctamente y que seed_customers()
solo inserta datos cuando la tabla está vacía.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from models import Base, Customer
from seed import seed_customers


# ── Fixture: BD en memoria aislada por cada test ──────────────────────────────

@pytest.fixture
def db_session():
    """Sesión SQLite en memoria; esquema creado y destruido por test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Tests de esquema ──────────────────────────────────────────────────────────

def test_customer_table_has_all_columns(db_session):
    """La tabla customers contiene las 9 columnas definidas en la spec."""
    col_names = {col.name for col in Customer.__table__.columns}
    expected = {
        "id", "full_name", "email", "phone",
        "delivery_address", "coverage_zone",
        "is_active", "created_at", "updated_at",
    }
    assert expected == col_names, f"Columnas inesperadas o faltantes: {col_names ^ expected}"


def test_customer_email_is_unique(db_session):
    """El campo email tiene restricción UNIQUE: insertar duplicado lanza IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    db_session.add(Customer(
        full_name="Usuario A",
        email="duplicado@ejemplo.com",
        phone="5550000001",
        delivery_address="Calle A 1",
        coverage_zone="Local",
    ))
    db_session.commit()

    db_session.add(Customer(
        full_name="Usuario B",
        email="duplicado@ejemplo.com",  # mismo email
        phone="5550000002",
        delivery_address="Calle B 2",
        coverage_zone="Regional",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_customer_is_active_defaults_true(db_session):
    """Un cliente nuevo tiene is_active=True por defecto."""
    customer = Customer(
        full_name="Test User",
        email="test@ejemplo.com",
        phone="5551234567",
        delivery_address="Calle Test 1",
        coverage_zone="Local",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    assert customer.is_active is True


def test_customer_created_at_set_automatically(db_session):
    """created_at se asigna automáticamente al insertar."""
    customer = Customer(
        full_name="Fecha Test",
        email="fecha@ejemplo.com",
        phone="5550000000",
        delivery_address="Av. Fecha 100",
        coverage_zone="Nacional",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    assert customer.created_at is not None


# ── Tests de seed ─────────────────────────────────────────────────────────────

def test_seed_inserts_between_3_and_5_customers(db_session):
    """seed_customers() inserta entre 3 y 5 clientes en BD vacía."""
    seed_customers(db_session)
    count = db_session.query(Customer).count()
    assert 3 <= count <= 5, f"Se esperaban 3-5 clientes, se obtuvieron: {count}"


def test_seed_does_not_run_when_data_exists(db_session):
    """seed_customers() NO inserta registros si la tabla ya tiene datos."""
    seed_customers(db_session)
    count_after_first = db_session.query(Customer).count()

    seed_customers(db_session)  # segunda llamada — no debe agregar nada
    count_after_second = db_session.query(Customer).count()

    assert count_after_first == count_after_second, \
        "seed_customers() no debe insertar si ya existen registros"


def test_seed_customers_have_required_fields(db_session):
    """Cada cliente semilla tiene todos los campos requeridos no vacíos."""
    seed_customers(db_session)
    customers = db_session.query(Customer).all()
    for c in customers:
        assert c.full_name and len(c.full_name) > 0, f"full_name vacío en id={c.id}"
        assert c.email and "@" in c.email, f"email inválido en id={c.id}: {c.email}"
        assert c.phone and len(c.phone) > 0, f"phone vacío en id={c.id}"
        assert c.delivery_address and len(c.delivery_address) > 0, f"delivery_address vacío en id={c.id}"
        assert c.coverage_zone and len(c.coverage_zone) > 0, f"coverage_zone vacío en id={c.id}"


def test_seed_has_varied_coverage_zones(db_session):
    """Los clientes semilla cubren al menos 2 zonas distintas."""
    seed_customers(db_session)
    zones = {c.coverage_zone for c in db_session.query(Customer).all()}
    assert len(zones) >= 2, f"Se esperan ≥2 zonas distintas, se encontraron: {zones}"


def test_seed_has_mixed_active_status(db_session):
    """Los clientes semilla incluyen al menos un cliente inactivo (para pruebas)."""
    seed_customers(db_session)
    inactive = db_session.query(Customer).filter(Customer.is_active == False).count()
    assert inactive >= 1, "El seed debe incluir al menos un cliente inactivo para facilitar pruebas"
