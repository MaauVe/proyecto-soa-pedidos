"""
Servicio Orquestador de Pedidos — Puerto 8004
Coordina la creación, consulta y cancelación de pedidos integrando:
- servicio-clientes (8001)
- servicio-inventario (8002)
- servicio-envios (8003)
"""
import logging
import math
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

import clients
import config
from auth import verify_api_key
from database import get_db, init_db
from schemas import (
    HealthResponse,
    OrderCreate,
    OrderListResponse,
    OrderResponse,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=config.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("servicio-pedidos")


# ── Lifespan (arranque y apagado) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD al arrancar; libera recursos al apagar."""
    logger.info("Arrancando servicio-pedidos en puerto %s...", config.PORT)
    init_db()
    yield
    logger.info("Apagando servicio-pedidos.")


# ── Aplicación FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Servicio Orquestador de Pedidos",
    description=(
        "API REST del orquestador del sistema SOA de pedidos y entregas. "
        "Coordina por HTTP la validación de clientes, reserva y liberación de inventario (Saga), "
        "cotización y despacho de envíos, y persiste el estado canónico de los pedidos."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers de Compensación (Saga) ───────────────────────────────────────────
def _compensate_stock(items: list[dict]) -> tuple[bool, Optional[str]]:
    """
    Intenta liberar las existencias previamente reservadas en servicio-inventario.
    Retorna (True, None) si la liberación fue exitosa.
    Retorna (False, str_error) si la compensación falló.
    """
    try:
        logger.info("Ejecutando compensación de stock para %d productos...", len(items))
        clients.release_stock(items)
        logger.info("Compensación de stock completada exitosamente.")
        return True, None
    except Exception as exc:
        err_msg = f"Fallo al liberar stock en inventario: {exc}"
        logger.critical("ERROR CRÍTICO: %s", err_msg)
        return False, err_msg


# ── Endpoints Públicos ────────────────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["Salud"],
    summary="Verificar estado de salud del servicio",
    description="Endpoint público sin autenticación para monitoreo de disponibilidad.",
)
def health_check() -> HealthResponse:
    """Retorna el estado de salud, versión y puerto del servicio."""
    return HealthResponse(
        service="servicio-pedidos",
        status="ok",
        version="0.1.0",
        port=config.PORT,
    )


# ── Endpoints de Pedidos ───────────────────────────────────────────────────────
@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Pedidos"],
    summary="Crear nuevo pedido (Flujo Orquestado + Saga)",
    description=(
        "Orquesta la creación de un pedido en 5 pasos: "
        "1) Valida cliente en servicio-clientes; "
        "2) Reserva stock en servicio-inventario; "
        "3) Cotiza envío en servicio-envios; "
        "4) Persiste el pedido y líneas en SQLite; "
        "5) Registra la guía de envío en servicio-envios. "
        "Si ocurre un fallo tras reservar stock, compensa automáticamente liberando el inventario."
    ),
)
def create_order(
    order_in: OrderCreate,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> dict:
    """Crea y orquesta un pedido completo con compensación Saga ante fallos."""
    logger.info("Iniciando orquestación de pedido para cliente ID: %s", order_in.customer_id)

    # ── Paso 1: Validar cliente ───────────────────────────────────────────────
    customer_info = clients.validate_customer(order_in.customer_id)
    customer_name = customer_info["full_name"]
    coverage_zone = customer_info["coverage_zone"]
    logger.info("Cliente validado: '%s' (Zona: %s)", customer_name, coverage_zone)

    # ── Paso 2: Reservar stock en servicio-inventario ──────────────────────────
    reserve_payload = [
        {"product_id": it.product_id, "quantity": it.quantity}
        for it in order_in.items
    ]
    reserve_res = clients.reserve_stock(reserve_payload)
    reserved_items = reserve_res.get("reserved", [])
    logger.info("Stock reservado exitosamente para %d productos.", len(reserved_items))

    # A partir de aquí, el stock está descontado; si algo falla, requerimos compensar
    items_to_release = [
        {"product_id": item["product_id"], "quantity": item["quantity_reserved"]}
        for item in reserved_items
    ]
    reserved_map = {item["product_id"]: item for item in reserved_items}

    # ── Paso 3: Cotizar envío en servicio-envios ──────────────────────────────
    try:
        shipping_cost = clients.quote_shipment(coverage_zone)
        logger.info("Costo de envío cotizado para zona %s: %s", coverage_zone, shipping_cost)
    except Exception as exc:
        logger.error("Fallo en cotización de envío: %s. Ejecutando compensación...", exc)
        success, comp_err = _compensate_stock(items_to_release)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error crítico: el pedido falló y la compensación de stock no pudo completarse. Requiere intervención manual.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de cotización de envíos no está disponible.",
        ) from exc

    # ── Paso 4: Persistencia atómica local en pedidos.db ───────────────────────
    now_iso = datetime.now(UTC).isoformat()
    lines_to_insert = []
    items_total = 0.0

    for item_in in order_in.items:
        res_info = reserved_map.get(item_in.product_id, {})
        p_name = res_info.get("name", f"Producto {item_in.product_id}")
        u_price = float(res_info.get("unit_price", 0.0))
        subtotal = round(u_price * item_in.quantity, 2)
        items_total += subtotal
        lines_to_insert.append((
            item_in.product_id,
            p_name,
            u_price,
            item_in.quantity,
            subtotal,
        ))

    total_amount = round(items_total + shipping_cost, 2)

    try:
        cursor = db.cursor()
        with db:
            cursor.execute(
                """
                INSERT INTO orders (customer_id, customer_name, coverage_zone, shipping_cost,
                                    total_amount, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?);
                """,
                (
                    order_in.customer_id,
                    customer_name,
                    coverage_zone,
                    shipping_cost,
                    total_amount,
                    now_iso,
                    now_iso,
                ),
            )
            order_id = cursor.lastrowid

            for line in lines_to_insert:
                cursor.execute(
                    """
                    INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (order_id, line[0], line[1], line[2], line[3], line[4]),
                )
        logger.info("Pedido ID %s persistido en pedidos.db con estado PENDING.", order_id)
    except Exception as exc:
        logger.error("Fallo al persistir pedido en base de datos: %s. Compensando...", exc)
        success, comp_err = _compensate_stock(items_to_release)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error crítico: el pedido falló y la compensación de stock no pudo completarse. Requiere intervención manual.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al persistir el pedido.",
        ) from exc

    # ── Paso 5: Registrar guía de envío en servicio-envios ─────────────────────
    try:
        shipment_data = clients.create_shipment(order_id, coverage_zone, customer_name)
        shipment_id = shipment_data.get("id")
        logger.info("Guía de envío registrada exitosamente con ID %s para pedido %s.", shipment_id, order_id)
    except Exception as exc:
        logger.error("Fallo al registrar guía de envío para pedido %s: %s. Ejecutando compensación...", order_id, exc)
        success, comp_err = _compensate_stock(items_to_release)
        if success:
            try:
                with db:
                    db.execute("DELETE FROM order_items WHERE order_id = ?;", (order_id,))
                    db.execute("DELETE FROM orders WHERE id = ?;", (order_id,))
                logger.info("Pedido ID %s eliminado de BD tras compensación exitosa.", order_id)
            except Exception as del_exc:
                logger.error("Error al limpiar pedido tras compensación: %s", del_exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="No fue posible registrar la guía de envío.",
            ) from exc
        else:
            failed_iso = datetime.now(UTC).isoformat()
            try:
                with db:
                    db.execute(
                        "UPDATE orders SET status = 'FAILED', compensation_error = ?, updated_at = ? WHERE id = ?;",
                        (comp_err, failed_iso, order_id),
                    )
                logger.warning("Pedido ID %s marcado como FAILED debido a fallo de compensación.", order_id)
            except Exception as update_exc:
                logger.critical("Error al actualizar pedido a FAILED: %s", update_exc)

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error crítico: el pedido falló y la compensación de stock no pudo completarse. Requiere intervención manual.",
            ) from exc

    # ── Éxito: Confirmar pedido ───────────────────────────────────────────────
    confirmed_iso = datetime.now(UTC).isoformat()
    with db:
        db.execute(
            "UPDATE orders SET status = 'CONFIRMED', shipment_id = ?, updated_at = ? WHERE id = ?;",
            (shipment_id, confirmed_iso, order_id),
        )

    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
    order_row = dict(cursor.fetchone())

    cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC;", (order_id,))
    items_rows = [dict(r) for r in cursor.fetchall()]

    order_row["items"] = items_rows
    order_row["shipment_status"] = "PENDING"
    order_row["shipment_detail"] = None

    logger.info("Pedido ID %s confirmado exitosamente (Shipment ID: %s).", order_id, shipment_id)
    return order_row


@app.get(
    "/orders/{order_id}",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    tags=["Pedidos"],
    summary="Consultar pedido por ID con estado de envío enriquecido",
    description=(
        "Retorna la información completa de un pedido con sus líneas. "
        "Consulta el estado en tiempo real en servicio-envios. Si el servicio de envíos no responde, "
        "retorna la respuesta degradada con shipment_status: null y aviso explicativo."
    ),
)
def get_order(
    order_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> dict:
    """Consulta un pedido por su ID con enriquecimiento de envío degradable."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning("Pedido no encontrado con ID: %s", order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado.",
        )

    order_dict = dict(row)

    cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC;", (order_id,))
    order_dict["items"] = [dict(r) for r in cursor.fetchall()]

    shipment_id = order_dict.get("shipment_id")
    if shipment_id:
        shipment_data = clients.get_shipment(shipment_id)
        if shipment_data:
            order_dict["shipment_status"] = shipment_data.get("status")
            order_dict["shipment_detail"] = None
        else:
            order_dict["shipment_status"] = None
            order_dict["shipment_detail"] = "No disponible temporalmente"
    else:
        order_dict["shipment_status"] = None
        order_dict["shipment_detail"] = None

    return order_dict


@app.get(
    "/orders",
    response_model=OrderListResponse,
    status_code=status.HTTP_200_OK,
    tags=["Pedidos"],
    summary="Listado paginado de pedidos",
    description="Retorna el listado paginado de pedidos persistidos en pedidos.db con filtros opcionales.",
)
def list_orders(
    page: int = Query(default=1, ge=1, description="Número de página (>= 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Cantidad por página (1 a 100)"),
    status: Optional[str] = Query(default=None, description="Filtrar por estado del pedido"),
    customer_id: Optional[int] = Query(default=None, ge=1, description="Filtrar por cliente"),
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> dict:
    """Lista pedidos paginados con filtros opcionales."""
    cursor = db.cursor()
    where_clauses = []
    params = []

    if status:
        where_clauses.append("status = ?")
        params.append(status.upper())

    if customer_id:
        where_clauses.append("customer_id = ?")
        params.append(customer_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    cursor.execute(f"SELECT COUNT(*) AS total FROM orders {where_sql};", params)
    total = cursor.fetchone()["total"]
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    offset = (page - 1) * page_size
    query = f"""
        SELECT id, customer_id, customer_name, coverage_zone, status, total_amount,
               shipment_id, created_at, updated_at
        FROM orders
        {where_sql}
        ORDER BY id DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(query, params + [page_size, offset])
    items = [dict(r) for r in cursor.fetchall()]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.patch(
    "/orders/{order_id}/cancel",
    response_model=OrderResponse,
    status_code=status.HTTP_200_OK,
    tags=["Pedidos"],
    summary="Cancelar pedido activo",
    description=(
        "Cancela un pedido activo verificando el estado del envío en servicio-envios. "
        "Si el envío está en PENDING, cancela el envío, libera el inventario y marca el pedido como CANCELLED. "
        "Si está en IN_TRANSIT o DELIVERED, rechaza con 409."
    ),
)
def cancel_order(
    order_id: int,
    db: sqlite3.Connection = Depends(get_db),
    _: str = Depends(verify_api_key),
) -> dict:
    """Cancela un pedido y libera el inventario si el envío no ha salido a reparto."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
    row = cursor.fetchone()
    if not row:
        logger.warning("Intento de cancelar pedido inexistente con ID: %s", order_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado.",
        )

    order_dict = dict(row)
    current_status = order_dict["status"]

    if current_status in ("CANCELLED", "FAILED"):
        logger.warning("Pedido %s ya se encuentra en estado terminal '%s'.", order_id, current_status)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El pedido no puede cancelarse porque ya está en estado terminal.",
        )

    shipment_id = order_dict.get("shipment_id")
    # Obtener las líneas del pedido para liberar inventario
    cursor.execute("SELECT product_id, quantity FROM order_items WHERE order_id = ?;", (order_id,))
    items_to_release = [
        {"product_id": r["product_id"], "quantity": r["quantity"]}
        for r in cursor.fetchall()
    ]

    # Verificar estado del envío si shipment_id existe
    if shipment_id:
        shipment_data = clients.get_shipment(shipment_id)
        if not shipment_data:
            logger.error("No fue posible consultar el envío %s para cancelar pedido %s.", shipment_id, order_id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="El servicio de envíos no está disponible.",
            )

        shipment_status = shipment_data.get("status")
        if shipment_status in ("IN_TRANSIT", "DELIVERED"):
            logger.warning("Cancelación rechazada para pedido %s: envío en estado '%s'.", order_id, shipment_status)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede cancelar un pedido cuyo envío ya está en tránsito o entregado.",
            )

        if shipment_status == "PENDING":
            clients.cancel_shipment(shipment_id)
            logger.info("Envío %s cancelado en servicio-envios.", shipment_id)
        elif shipment_status == "CANCELLED":
            logger.info("Envío %s ya estaba cancelado previamente.", shipment_id)

    # Liberar el stock reservado en servicio-inventario
    if items_to_release:
        clients.release_stock(items_to_release)
        logger.info("Stock liberado exitosamente al cancelar pedido %s.", order_id)

    # Actualizar estado local del pedido a CANCELLED
    now_iso = datetime.now(UTC).isoformat()
    with db:
        db.execute(
            "UPDATE orders SET status = 'CANCELLED', updated_at = ? WHERE id = ?;",
            (now_iso, order_id),
        )

    # Retornar el pedido completo actualizado
    cursor.execute("SELECT * FROM orders WHERE id = ?;", (order_id,))
    updated_order = dict(cursor.fetchone())

    cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id ASC;", (order_id,))
    updated_order["items"] = [dict(r) for r in cursor.fetchall()]
    updated_order["shipment_status"] = "CANCELLED" if shipment_id else None
    updated_order["shipment_detail"] = None

    logger.info("Pedido ID %s cancelado exitosamente.", order_id)
    return updated_order
