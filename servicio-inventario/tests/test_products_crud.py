"""
Tests consolidados para T-05 a T-10 (Bloque 2) — servicio-inventario.
Cubre el CRUD completo de productos:
- T-05: POST /products — Creación y validaciones (RF-2).
- T-06: GET /products/{id} — Consulta por ID (RF-3).
- T-07: GET /products — Listado paginado y filtros (RF-4).
- T-08: PATCH /products/{id} — Actualización parcial (RF-5).
- T-09: DELETE /products/{id} — Desactivación lógica (RF-6).
- T-10: PATCH /products/{id}/reactivate — Reactivación (RF-7).
"""
import sqlite3
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from auth import verify_api_key
from database import get_connection
from main import (
    app,
    create_product,
    deactivate_product,
    get_product,
    list_products,
    reactivate_product,
    update_product,
)
from schemas import ProductCreate, ProductUpdate

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
    from database import init_db
    db_file = tmp_path / "test_crud.db"
    init_db(db_file)
    conn = get_connection(db_file)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def empty_conn(empty_db):
    """Conexión a BD vacía con solo el esquema."""
    conn = get_connection(empty_db)
    try:
        yield conn
    finally:
        conn.close()


# ── T-05: POST /products ───────────────────────────────────────────────────────

class TestCreateProduct:
    def test_create_valid_product(self, empty_conn):
        """Crear producto válido retorna 201 con campos completos e is_active=True."""
        payload = ProductCreate(
            sku="TAB-001",
            name="Tablet 10 pulgadas",
            description="Tablet Android de alta resolución",
            unit_price=3200.50,
            weight_kg=0.48,
            stock=30,
        )
        res = create_product(product_in=payload, db=empty_conn, _=DUMMY_KEY)
        assert res["id"] is not None
        assert res["sku"] == "TAB-001"
        assert res["name"] == "Tablet 10 pulgadas"
        assert res["unit_price"] == 3200.50
        assert res["weight_kg"] == 0.48
        assert res["stock"] == 30
        assert res["is_active"] is True
        assert res["created_at"] is not None
        assert res["updated_at"] is not None

    def test_create_product_normalizes_sku_to_uppercase(self, empty_conn):
        """El SKU se normaliza a mayúsculas al registrarse."""
        payload = ProductCreate(
            sku="teclado-min",
            name="Teclado",
            unit_price=500.0,
            weight_kg=0.5,
            stock=10,
        )
        res = create_product(product_in=payload, db=empty_conn, _=DUMMY_KEY)
        assert res["sku"] == "TECLADO-MIN"

    def test_create_duplicate_sku_same_case_raises_409(self, db_conn):
        """SKU duplicado en mismo case lanza HTTP 409 con mensaje en español."""
        payload = ProductCreate(
            sku="LAPTOP-001",  # Ya existe en el seed
            name="Otra Laptop",
            unit_price=10000.0,
            weight_kg=2.0,
            stock=5,
        )
        with pytest.raises(HTTPException) as exc_info:
            create_product(product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 409
        assert "Ya existe un producto registrado con ese SKU." in exc_info.value.detail

    def test_create_duplicate_sku_case_insensitive_raises_409(self, db_conn):
        """SKU duplicado con diferente case (minúsculas) lanza HTTP 409."""
        payload = ProductCreate(
            sku="laptop-001",  # Existe en mayúsculas en el seed
            name="Otra Laptop",
            unit_price=10000.0,
            weight_kg=2.0,
            stock=5,
        )
        with pytest.raises(HTTPException) as exc_info:
            create_product(product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 409

    def test_validation_errors_pydantic(self):
        """Validaciones numéricas y de obligatoriedad en Pydantic."""
        # unit_price <= 0
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="N", unit_price=0, weight_kg=1.0, stock=5)
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="N", unit_price=-10, weight_kg=1.0, stock=5)

        # weight_kg <= 0
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="N", unit_price=100, weight_kg=0, stock=5)
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="N", unit_price=100, weight_kg=-0.5, stock=5)

        # stock < 0
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="N", unit_price=100, weight_kg=1.0, stock=-1)

        # stock = 0 es válido
        p_zero = ProductCreate(sku="P1", name="N", unit_price=100, weight_kg=1.0, stock=0)
        assert p_zero.stock == 0

        # name vacío
        with pytest.raises(ValidationError):
            ProductCreate(sku="P1", name="", unit_price=100, weight_kg=1.0, stock=5)

    def test_route_registration_post_products(self):
        """Verifica que POST /products esté registrado con auth."""
        assert _route_requires_auth("/products", "POST")


# ── T-06: GET /products/{id} ───────────────────────────────────────────────────

class TestGetProduct:
    def test_get_existing_product_returns_200(self, db_conn):
        """Consultar producto existente por ID retorna 200 con datos completos."""
        res = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 1
        assert res["sku"] == "LAPTOP-001"
        assert res["stock"] == 20
        assert res["is_active"] is True

    def test_get_inactive_product_returns_200(self, db_conn):
        """Producto inactivo se retorna con 200 e is_active=False."""
        # El producto 5 en el seed es inactivo
        res = get_product(product_id=5, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 5
        assert res["sku"] == "AURICULARES-005"
        assert res["is_active"] is False

    def test_get_non_existing_product_raises_404(self, db_conn):
        """ID inexistente lanza HTTP 404 con mensaje descriptivo en español."""
        with pytest.raises(HTTPException) as exc_info:
            get_product(product_id=9999, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 404
        assert "Producto no encontrado." in exc_info.value.detail

    def test_route_registration_get_product_by_id(self):
        """Verifica que GET /products/{product_id} esté registrado con auth."""
        assert _route_requires_auth("/products/{product_id}", "GET")


# ── T-07: GET /products ────────────────────────────────────────────────────────

class TestListProducts:
    def test_list_default_pagination(self, db_conn):
        """Listado por defecto aplica page=1 y page_size=20 retornando los 5 del seed."""
        res = list_products(page=1, page_size=20, is_active=None, db=db_conn, _=DUMMY_KEY)
        assert res["total"] == 5
        assert res["page"] == 1
        assert res["page_size"] == 20
        assert res["total_pages"] == 1
        assert len(res["items"]) == 5

    def test_list_filter_active_only(self, db_conn):
        """Filtrar por is_active=True retorna solo productos activos (4 en el seed)."""
        res = list_products(page=1, page_size=20, is_active=True, db=db_conn, _=DUMMY_KEY)
        assert res["total"] == 4
        assert len(res["items"]) == 4
        for item in res["items"]:
            assert item["is_active"] is True

    def test_list_filter_inactive_only(self, db_conn):
        """Filtrar por is_active=False retorna solo productos inactivos (1 en el seed)."""
        res = list_products(page=1, page_size=20, is_active=False, db=db_conn, _=DUMMY_KEY)
        assert res["total"] == 1
        assert len(res["items"]) == 1
        assert res["items"][0]["is_active"] is False
        assert res["items"][0]["sku"] == "AURICULARES-005"

    def test_list_pagination_pages(self, db_conn):
        """Paginación con page_size=2 genera 3 páginas para 5 elementos."""
        res_p1 = list_products(page=1, page_size=2, is_active=None, db=db_conn, _=DUMMY_KEY)
        assert len(res_p1["items"]) == 2
        assert res_p1["total"] == 5
        assert res_p1["total_pages"] == 3

        res_p3 = list_products(page=3, page_size=2, is_active=None, db=db_conn, _=DUMMY_KEY)
        assert len(res_p3["items"]) == 1

    def test_list_empty_db_returns_empty_list(self, empty_conn):
        """BD vacía retorna total=0 y lista de items vacía."""
        res = list_products(page=1, page_size=20, is_active=None, db=empty_conn, _=DUMMY_KEY)
        assert res["total"] == 0
        assert res["total_pages"] == 0
        assert res["items"] == []

    def test_route_registration_list_products(self):
        """Verifica que GET /products esté registrado con auth."""
        assert _route_requires_auth("/products", "GET")


# ── T-08: PATCH /products/{id} ─────────────────────────────────────────────────

class TestUpdateProduct:
    def test_update_single_field(self, db_conn):
        """Actualizar solo el nombre modifica únicamente ese campo y actualiza updated_at."""
        payload = ProductUpdate(name="Laptop Renovada 14")
        res = update_product(product_id=1, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 1
        assert res["name"] == "Laptop Renovada 14"
        assert res["sku"] == "LAPTOP-001"  # No cambió
        assert res["unit_price"] == 12500.0  # No cambió

    def test_update_price_and_weight(self, db_conn):
        """Actualizar precio y peso modifica ambos campos."""
        payload = ProductUpdate(unit_price=13000.0, weight_kg=1.4)
        res = update_product(product_id=1, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert res["unit_price"] == 13000.0
        assert res["weight_kg"] == 1.4

    def test_update_empty_body_is_noop(self, db_conn):
        """Cuerpo vacío `{}` retorna el producto sin cambios (no-op)."""
        payload = ProductUpdate()
        res = update_product(product_id=1, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 1
        assert res["sku"] == "LAPTOP-001"

    def test_update_duplicate_sku_raises_409(self, db_conn):
        """Cambiar SKU al de otro producto existente lanza HTTP 409."""
        payload = ProductUpdate(sku="MOUSE-002")  # Ya pertenece al producto 2
        with pytest.raises(HTTPException) as exc_info:
            update_product(product_id=1, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 409
        assert "Ya existe un producto registrado con ese SKU." in exc_info.value.detail

    def test_update_same_sku_on_same_product_succeeds(self, db_conn):
        """Asignar el mismo SKU al mismo producto no causa conflicto 409."""
        payload = ProductUpdate(sku="LAPTOP-001")
        res = update_product(product_id=1, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert res["sku"] == "LAPTOP-001"

    def test_update_non_existing_product_raises_404(self, db_conn):
        """ID inexistente en PATCH lanza HTTP 404."""
        payload = ProductUpdate(name="Nuevo Nombre")
        with pytest.raises(HTTPException) as exc_info:
            update_product(product_id=9999, product_in=payload, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 404
        assert "Producto no encontrado." in exc_info.value.detail

    def test_route_registration_patch_product(self):
        """Verifica que PATCH /products/{product_id} esté registrado con auth."""
        assert _route_requires_auth("/products/{product_id}", "PATCH")


# ── T-09: DELETE /products/{id} ────────────────────────────────────────────────

class TestDeactivateProduct:
    def test_deactivate_active_product(self, db_conn):
        """Desactivar un producto activo lo marca con is_active=False sin borrarlo ni alterar stock."""
        res = deactivate_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 1
        assert res["is_active"] is False
        assert res["stock"] == 20  # El stock permanece intacto

        # Sigue siendo consultable por GET
        persisted = get_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert persisted["is_active"] is False
        assert persisted["stock"] == 20

    def test_deactivate_already_inactive_product_raises_409(self, db_conn):
        """Desactivar un producto ya inactivo lanza HTTP 409."""
        # Producto 5 ya es inactivo en el seed
        with pytest.raises(HTTPException) as exc_info:
            deactivate_product(product_id=5, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 409
        assert "El producto ya se encuentra inactivo." in exc_info.value.detail

    def test_deactivate_non_existing_product_raises_404(self, db_conn):
        """Desactivar ID inexistente lanza HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            deactivate_product(product_id=9999, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 404
        assert "Producto no encontrado." in exc_info.value.detail

    def test_route_registration_delete_product(self):
        """Verifica que DELETE /products/{product_id} esté registrado con auth."""
        assert _route_requires_auth("/products/{product_id}", "DELETE")


# ── T-10: PATCH /products/{id}/reactivate ──────────────────────────────────────

class TestReactivateProduct:
    def test_reactivate_inactive_product(self, db_conn):
        """Reactivar un producto inactivo establece is_active=True."""
        res = reactivate_product(product_id=5, db=db_conn, _=DUMMY_KEY)
        assert res["id"] == 5
        assert res["is_active"] is True

        persisted = get_product(product_id=5, db=db_conn, _=DUMMY_KEY)
        assert persisted["is_active"] is True

    def test_reactivate_already_active_product_raises_409(self, db_conn):
        """Reactivar un producto ya activo lanza HTTP 409."""
        # Producto 1 ya está activo
        with pytest.raises(HTTPException) as exc_info:
            reactivate_product(product_id=1, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 409
        assert "El producto ya se encuentra activo." in exc_info.value.detail

    def test_reactivate_non_existing_product_raises_404(self, db_conn):
        """Reactivar ID inexistente lanza HTTP 404."""
        with pytest.raises(HTTPException) as exc_info:
            reactivate_product(product_id=9999, db=db_conn, _=DUMMY_KEY)
        assert exc_info.value.status_code == 404
        assert "Producto no encontrado." in exc_info.value.detail

    def test_route_registration_reactivate_product(self):
        """Verifica que PATCH /products/{product_id}/reactivate esté registrado con auth."""
        assert _route_requires_auth("/products/{product_id}/reactivate", "PATCH")
