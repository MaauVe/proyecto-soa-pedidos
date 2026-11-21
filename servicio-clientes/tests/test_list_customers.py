"""
Tests T-06: Listado paginado de clientes - GET /customers (RF-4).
Pruebas de paginación por defecto, filtros por estado, base de datos vacía y metadatos de ruta.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from auth import verify_api_key
from main import app, list_customers
from models import Base, Customer
from schemas import CustomerListResponse


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


# ── Pruebas del endpoint list_customers ───────────────────────────────────────

class TestListCustomersEndpoint:
    def test_list_customers_empty_db_returns_200_empty_list(self, db_session):
        """En base de datos vacía, retorna HTTP 200 con items=[], total=0 y total_pages=0."""
        res = list_customers(page=1, page_size=20, is_active=None, db=db_session, _="mock_key")
        assert res["items"] == []
        assert res["total"] == 0
        assert res["page"] == 1
        assert res["page_size"] == 20
        assert res["total_pages"] == 0

    def test_list_customers_default_pagination(self, db_session):
        """Sin filtros específicos, retorna todos los clientes respetando defaults."""
        c1 = Customer(
            full_name="Cliente A",
            email="a@example.com",
            phone="111",
            delivery_address="Dir A",
            coverage_zone="Local",
            is_active=True,
        )
        c2 = Customer(
            full_name="Cliente B",
            email="b@example.com",
            phone="222",
            delivery_address="Dir B",
            coverage_zone="Regional",
            is_active=False,
        )
        db_session.add_all([c1, c2])
        db_session.commit()

        res = list_customers(page=1, page_size=20, is_active=None, db=db_session, _="mock_key")
        assert res["total"] == 2
        assert len(res["items"]) == 2
        assert res["total_pages"] == 1

    def test_list_customers_pagination_pages_and_sizes(self, db_session):
        """Valida que page y page_size dividan correctamente los elementos."""
        customers = [
            Customer(
                full_name=f"Cliente {i}",
                email=f"c{i}@example.com",
                phone=f"555000{i}",
                delivery_address=f"Calle {i}",
                coverage_zone="Local",
                is_active=True,
            )
            for i in range(1, 6)
        ]
        db_session.add_all(customers)
        db_session.commit()

        # Página 1 de 2 elementos
        p1 = list_customers(page=1, page_size=2, is_active=None, db=db_session, _="mock_key")
        assert p1["total"] == 5
        assert len(p1["items"]) == 2
        assert p1["total_pages"] == 3
        assert p1["items"][0].email == "c1@example.com"
        assert p1["items"][1].email == "c2@example.com"

        # Página 3 de 2 elementos (última página, solo 1 elemento)
        p3 = list_customers(page=3, page_size=2, is_active=None, db=db_session, _="mock_key")
        assert p3["total"] == 5
        assert len(p3["items"]) == 1
        assert p3["items"][0].email == "c5@example.com"

    def test_list_customers_filter_by_active_true(self, db_session):
        """Filtrar por is_active=True retorna únicamente clientes activos."""
        c_active = Customer(
            full_name="Activo",
            email="activo@example.com",
            phone="123",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=True,
        )
        c_inactive = Customer(
            full_name="Inactivo",
            email="inactivo@example.com",
            phone="456",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=False,
        )
        db_session.add_all([c_active, c_inactive])
        db_session.commit()

        res = list_customers(page=1, page_size=20, is_active=True, db=db_session, _="mock_key")
        assert res["total"] == 1
        assert len(res["items"]) == 1
        assert res["items"][0].is_active is True
        assert res["items"][0].email == "activo@example.com"

    def test_list_customers_filter_by_active_false(self, db_session):
        """Filtrar por is_active=False retorna únicamente clientes inactivos."""
        c_active = Customer(
            full_name="Activo",
            email="activo2@example.com",
            phone="123",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=True,
        )
        c_inactive = Customer(
            full_name="Inactivo",
            email="inactivo2@example.com",
            phone="456",
            delivery_address="Dir",
            coverage_zone="Local",
            is_active=False,
        )
        db_session.add_all([c_active, c_inactive])
        db_session.commit()

        res = list_customers(page=1, page_size=20, is_active=False, db=db_session, _="mock_key")
        assert res["total"] == 1
        assert len(res["items"]) == 1
        assert res["items"][0].is_active is False
        assert res["items"][0].email == "inactivo2@example.com"


# ── Verificación de Registro de Ruta en FastAPI ────────────────────────────────

class TestListCustomersRouteMetadata:
    def test_list_customers_route_registered(self):
        """La ruta GET /customers está registrada en la app."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route is not None, "Ruta GET /customers no registrada"

    def test_list_customers_status_code_is_200(self):
        """El endpoint GET /customers tiene status_code configurado en 200."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.status_code == 200

    def test_list_customers_response_model_is_correct(self):
        """El response_model es CustomerListResponse."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        assert route.response_model == CustomerListResponse

    def test_list_customers_requires_api_key(self):
        """La ruta GET /customers incluye la dependencia de autenticación verify_api_key."""
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "GET" in getattr(r, "methods", [])
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
        assert verify_api_key in all_deps, "GET /customers debe requerir verify_api_key"

    def test_list_customers_query_param_validations(self):
        """Verifica que page y page_size tengan las restricciones ge y le correspondientes."""
        import inspect
        route = next(
            (
                r
                for r in app.routes
                if getattr(r, "path", None) == "/customers" and "GET" in getattr(r, "methods", [])
            ),
            None,
        )
        sig = inspect.signature(route.endpoint)
        page_param = sig.parameters["page"].default
        page_size_param = sig.parameters["page_size"].default

        page_meta = {type(m).__name__: getattr(m, type(m).__name__.lower(), None) for m in page_param.metadata}
        page_size_meta = {type(m).__name__: getattr(m, type(m).__name__.lower(), None) for m in page_size_param.metadata}

        assert page_meta.get("Ge") == 1
        assert page_size_meta.get("Ge") == 1
        assert page_size_meta.get("Le") == 100
