"""
Servicio Orquestador de Pedidos — Puerto 8004
Coordina la creación, consulta y cancelación de pedidos integrando:
- servicio-clientes (8001)
- servicio-inventario (8002)
- servicio-envios (8003)
"""
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status

import clients
import config
from auth import verify_api_key
from database import get_db, init_db
from schemas import (
    HealthResponse,
    OrderCreate,
    OrderResponse,
    OrderItemResponse,
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

    # Recuperar pedido completo para responder
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
