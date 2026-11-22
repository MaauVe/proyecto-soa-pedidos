"""
Servicio de Catálogo e Inventario — Puerto 8002
Gestión de productos y existencias para el sistema SOA de pedidos y entregas.
"""
import logging
import math
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from auth import verify_api_key
from config import LOG_LEVEL, PORT
from database import get_db, init_db
from schemas import (
    CheckRequest,
    CheckResponse,
    HealthResponse,
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
    ReleaseRequest,
    ReleaseResponse,
    ReserveRequest,
    ReserveResponse,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("servicio-inventario")


# ── Lifespan (arranque y apagado) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD y el seed al arrancar; libera recursos al apagar."""
    logger.info("Arrancando servicio-inventario en puerto %s...", PORT)
    init_db()
    yield
    logger.info("Apagando servicio-inventario.")


# ── Aplicación FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="Servicio de Catálogo e Inventario",
    description=(
        "API REST para la gestión del catálogo de productos y control de existencias. "
        "Permite registrar, consultar, actualizar y desactivar productos, "
        "así como realizar reservas atómicas y liberación de stock para la orquestación de pedidos."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convierte un sqlite3.Row en dict normalizando is_active a booleano."""
    d = dict(row)
    d["is_active"] = bool(d["is_active"])
    return d


# ── Endpoints Base ─────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Sistema"],
    summary="Verificación de salud del servicio",
    response_description="Estado operativo del servicio",
)
def health_check():
    """
    Retorna el estado de salud del servicio.
    Este endpoint es público y no requiere autenticación por X-API-Key.
    """
    logger.info("Health check solicitado")
    return {
        "service": "servicio-inventario",
        "version": "0.1.0",
        "status": "ok",
        "port": PORT,
    }


# ── CRUD de Productos (T-05 a T-10) ────────────────────────────────────────────

@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Productos"],
    summary="Crear un nuevo producto",
    description="Registra un producto en el catálogo validando la unicidad del SKU.",
)
def create_product(
    product_in: ProductCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Registra un nuevo producto con is_active=true.
    Retorna HTTP 409 si el SKU ya se encuentra registrado (case-insensitive).
    """
    clean_sku = product_in.sku.strip().upper()
    cursor = db.cursor()
    cursor.execute("SELECT id FROM products WHERE UPPER(sku) = ?;", (clean_sku,))
    if cursor.fetchone():
        logger.warning("Conflicto al crear producto: SKU '%s' ya registrado.", clean_sku)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un producto registrado con ese SKU.",
        )

    now_iso = datetime.now(UTC).isoformat()
    with db:
        cursor.execute(
            """
            INSERT INTO products (sku, name, description, unit_price, weight_kg, stock, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?);
            """,
            (
                clean_sku,
                product_in.name.strip(),
                product_in.description.strip() if product_in.description else None,
                product_in.unit_price,
                product_in.weight_kg,
                product_in.stock,
                now_iso,
                now_iso,
            ),
        )
        product_id = cursor.lastrowid
        cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
        row = cursor.fetchone()

    logger.info("Producto creado exitosamente con ID %s (SKU: %s).", product_id, clean_sku)
    return _row_to_dict(row)


@app.get(
    "/products",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    tags=["Productos"],
    summary="Listar productos paginados",
    description="Obtiene el catálogo de productos con paginación y filtro opcional por estado activo.",
)
def list_products(
    page: int = Query(default=1, ge=1, description="Número de página (>= 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Tamaño de página (1 a 100)"),
    is_active: Optional[bool] = Query(default=None, description="Filtrar por estado activo/inactivo"),
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Retorna la lista paginada de productos con metadatos de paginación.
    """
    cursor = db.cursor()
    where_clauses = []
    params = []
    if is_active is not None:
        where_clauses.append("is_active = ?")
        params.append(1 if is_active else 0)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    cursor.execute(f"SELECT COUNT(*) AS total FROM products {where_sql};", params)
    row_count = cursor.fetchone()
    total = row_count["total"] if isinstance(row_count, sqlite3.Row) else row_count[0]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    offset = (page - 1) * page_size
    query = f"SELECT * FROM products {where_sql} ORDER BY id ASC LIMIT ? OFFSET ?;"
    cursor.execute(query, params + [page_size, offset])
    rows = cursor.fetchall()

    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    tags=["Productos"],
    summary="Consultar producto por ID",
    description="Retorna la información completa de un producto por su identificador único.",
)
def get_product(
    product_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Consulta un producto por su ID.
    Retorna HTTP 404 si el producto no existe.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning("Producto no encontrado con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )
    return _row_to_dict(row)


@app.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    tags=["Productos"],
    summary="Actualización parcial de producto",
    description="Actualiza uno o varios campos de un producto existente.",
)
def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Actualiza parcialmente los datos de un producto.
    Retorna HTTP 404 si el producto no existe.
    Retorna HTTP 409 si el SKU nuevo ya pertenece a otro producto.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    current = cursor.fetchone()
    if not current:
        logger.warning("Producto no encontrado para actualizar con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    update_data = product_in.model_dump(exclude_unset=True)
    if not update_data:
        return _row_to_dict(current)

    if "sku" in update_data and update_data["sku"] is not None:
        new_sku = update_data["sku"].strip().upper()
        cursor.execute(
            "SELECT id FROM products WHERE UPPER(sku) = ? AND id != ?;",
            (new_sku, product_id),
        )
        if cursor.fetchone():
            logger.warning("Conflicto al actualizar producto ID %s: SKU '%s' ya registrado.", product_id, new_sku)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un producto registrado con ese SKU.",
            )
        update_data["sku"] = new_sku

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    if "description" in update_data and update_data["description"] is not None:
        update_data["description"] = update_data["description"].strip()

    now_iso = datetime.now(UTC).isoformat()
    fields = [f"{k} = ?" for k in update_data.keys()]
    values = list(update_data.values())
    fields.append("updated_at = ?")
    values.append(now_iso)
    values.append(product_id)

    with db:
        db.execute(f"UPDATE products SET {', '.join(fields)} WHERE id = ?;", values)
        cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
        updated = cursor.fetchone()

    logger.info("Producto ID %s actualizado exitosamente.", product_id)
    return _row_to_dict(updated)


@app.delete(
    "/products/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    tags=["Productos"],
    summary="Desactivar producto (borrado lógico)",
    description="Desactiva un producto marcando is_active=false. El stock y el registro se conservan.",
)
def deactivate_product(
    product_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Desactiva un producto (borrado lógico).
    Retorna HTTP 404 si el producto no existe.
    Retorna HTTP 409 si el producto ya se encuentra inactivo.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning("Producto no encontrado para desactivar con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    if row["is_active"] == 0:
        logger.warning("Intento de desactivar producto ya inactivo con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El producto ya se encuentra inactivo.",
        )

    now_iso = datetime.now(UTC).isoformat()
    with db:
        db.execute(
            "UPDATE products SET is_active = 0, updated_at = ? WHERE id = ?;",
            (now_iso, product_id),
        )
        cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
        updated = cursor.fetchone()

    logger.info("Producto ID %s desactivado exitosamente (borrado lógico).", product_id)
    return _row_to_dict(updated)


@app.patch(
    "/products/{product_id}/reactivate",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    tags=["Productos"],
    summary="Reactivar un producto",
    description="Reactiva un producto previamente desactivado marcando is_active=true.",
)
def reactivate_product(
    product_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Reactiva un producto previamente desactivado.
    Retorna HTTP 404 si el producto no existe.
    Retorna HTTP 409 si el producto ya se encuentra activo.
    """
    cursor = db.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning("Producto no encontrado para reactivar con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Producto no encontrado.",
        )

    if row["is_active"] == 1:
        logger.warning("Intento de reactivar producto ya activo con ID: %s", product_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El producto ya se encuentra activo.",
        )

    now_iso = datetime.now(UTC).isoformat()
    with db:
        db.execute(
            "UPDATE products SET is_active = 1, updated_at = ? WHERE id = ?;",
            (now_iso, product_id),
        )
        cursor.execute("SELECT * FROM products WHERE id = ?;", (product_id,))
        updated = cursor.fetchone()

    logger.info("Producto ID %s reactivado exitosamente.", product_id)
    return _row_to_dict(updated)


# ── Operaciones Atómicas de Stock (T-11 a T-13) ────────────────────────────────

@app.post(
    "/products/reserve",
    response_model=ReserveResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inventario"],
    summary="Reserva atómica de stock",
    description="Valida disponibilidad y descuenta stock atómicamente para una lista de productos. Si algún ítem falla, aplica rollback total y retorna HTTP 409.",
)
def reserve_stock(
    reserve_in: ReserveRequest,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Descuenta existencias para múltiples productos en una transacción única.
    - Valida que todos los productos existan, estén activos y tengan stock suficiente.
    - Si alguno falla, ningún producto se descuenta y retorna HTTP 409.
    """
    cursor = db.cursor()
    errors = []
    items_to_reserve = []

    for item in reserve_in.items:
        cursor.execute(
            "SELECT id, name, unit_price, weight_kg, stock, is_active FROM products WHERE id = ?;",
            (item.product_id,),
        )
        row = cursor.fetchone()
        if not row:
            errors.append(f"El producto ID {item.product_id} no fue encontrado.")
            continue

        if row["is_active"] == 0:
            errors.append(f"El producto ID {item.product_id} ({row['name']}) se encuentra inactivo.")
            continue

        if row["stock"] < item.quantity:
            errors.append(
                f"Stock insuficiente para el producto ID {item.product_id} ({row['name']}): "
                f"solicitado {item.quantity}, disponible {row['stock']}."
            )
            continue

        items_to_reserve.append({
            "product_id": row["id"],
            "name": row["name"],
            "unit_price": row["unit_price"],
            "weight_kg": row["weight_kg"],
            "quantity_reserved": item.quantity,
            "stock_remaining": row["stock"] - item.quantity,
        })

    if errors:
        logger.warning("Fallo en reserva atómica de stock: %s", errors)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="; ".join(errors),
        )

    now_iso = datetime.now(UTC).isoformat()
    with db:
        for item in items_to_reserve:
            db.execute(
                "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?;",
                (item["stock_remaining"], now_iso, item["product_id"]),
            )

    logger.info("Reserva de stock exitosa para %d productos.", len(items_to_reserve))
    return {"reserved": items_to_reserve}


@app.post(
    "/products/release",
    response_model=ReleaseResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inventario"],
    summary="Liberación de stock",
    description="Restaura unidades de stock para pedidos cancelados o fallidos. Aplica incluso a productos inactivos.",
)
def release_stock(
    release_in: ReleaseRequest,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Restaura existencias sumando las cantidades liberadas.
    - Aplica incluso a productos inactivos.
    - Si algún product_id no existe, retorna HTTP 404 sin modificar el resto.
    """
    cursor = db.cursor()
    missing_ids = []
    items_to_release = []

    for item in release_in.items:
        cursor.execute("SELECT id, stock FROM products WHERE id = ?;", (item.product_id,))
        row = cursor.fetchone()
        if not row:
            missing_ids.append(item.product_id)
            continue
        new_stock = row["stock"] + item.quantity
        items_to_release.append({
            "product_id": row["id"],
            "quantity_released": item.quantity,
            "stock_after": new_stock,
        })

    if missing_ids:
        logger.warning("Fallo al liberar stock: productos no encontrados: %s", missing_ids)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto(s) no encontrado(s): ID(s) {missing_ids}.",
        )

    now_iso = datetime.now(UTC).isoformat()
    with db:
        for item in items_to_release:
            db.execute(
                "UPDATE products SET stock = ?, updated_at = ? WHERE id = ?;",
                (item["stock_after"], now_iso, item["product_id"]),
            )

    logger.info("Liberación de stock exitosa para %d productos.", len(items_to_release))
    return {"released": items_to_release}


@app.post(
    "/products/check-availability",
    response_model=CheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Inventario"],
    summary="Consulta de disponibilidad sin descuento",
    description="Verifica si uno o varios productos tienen stock suficiente y están activos sin modificar las existencias.",
)
def check_availability(
    check_in: CheckRequest,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Consulta informativa de disponibilidad de stock sin alterar existencias.
    Retorna HTTP 200 siempre con all_available y detalle por ítem.
    """
    cursor = db.cursor()
    all_available = True
    results = []

    for item in check_in.items:
        cursor.execute(
            "SELECT id, name, unit_price, weight_kg, stock, is_active FROM products WHERE id = ?;",
            (item.product_id,),
        )
        row = cursor.fetchone()
        if not row:
            all_available = False
            results.append({
                "product_id": item.product_id,
                "name": None,
                "unit_price": None,
                "weight_kg": None,
                "available": False,
                "stock_current": None,
                "quantity_requested": item.quantity,
                "reason": f"Producto no encontrado (ID {item.product_id})",
            })
            continue

        if row["is_active"] == 0:
            all_available = False
            results.append({
                "product_id": row["id"],
                "name": row["name"],
                "unit_price": row["unit_price"],
                "weight_kg": row["weight_kg"],
                "available": False,
                "stock_current": row["stock"],
                "quantity_requested": item.quantity,
                "reason": f"El producto ID {row['id']} se encuentra inactivo",
            })
            continue

        if row["stock"] < item.quantity:
            all_available = False
            results.append({
                "product_id": row["id"],
                "name": row["name"],
                "unit_price": row["unit_price"],
                "weight_kg": row["weight_kg"],
                "available": False,
                "stock_current": row["stock"],
                "quantity_requested": item.quantity,
                "reason": (
                    f"Stock insuficiente: solicitado {item.quantity}, disponible {row['stock']}"
                ),
            })
            continue

        results.append({
            "product_id": row["id"],
            "name": row["name"],
            "unit_price": row["unit_price"],
            "weight_kg": row["weight_kg"],
            "available": True,
            "stock_current": row["stock"],
            "quantity_requested": item.quantity,
            "reason": None,
        })

    return {
        "all_available": all_available,
        "results": results,
    }
