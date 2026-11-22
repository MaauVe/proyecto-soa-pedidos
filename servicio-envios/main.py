"""
Servicio de Envíos — Puerto 8003
Cotización de tarifas y gestión del ciclo de vida de entregas para el sistema SOA.
"""
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status

import config
from auth import verify_api_key
from database import get_db, init_db
from schemas import (
    HealthResponse,
    QuoteRequest,
    QuoteResponse,
    ShipmentCreate,
    ShipmentListResponse,
    ShipmentResponse,
    StatusEnum,
    StatusUpdateRequest,
    ZoneEnum,
    ZoneInfo,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=config.LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("servicio-envios")


# ── Helpers y Máquina de Estados ──────────────────────────────────────────────
ALLOWED_TRANSITIONS = {
    StatusEnum.PENDING: [StatusEnum.IN_TRANSIT, StatusEnum.CANCELLED],
    StatusEnum.IN_TRANSIT: [StatusEnum.DELIVERED, StatusEnum.CANCELLED],
    StatusEnum.DELIVERED: [],
    StatusEnum.CANCELLED: [],
}
TERMINAL_STATUSES = {StatusEnum.DELIVERED, StatusEnum.CANCELLED}


def get_zone_rate(zone: ZoneEnum) -> float:
    """Retorna la tarifa configurada en variables de entorno para la zona especificada."""
    rates = {
        ZoneEnum.LOCAL: config.RATE_LOCAL,
        ZoneEnum.REGIONAL: config.RATE_REGIONAL,
        ZoneEnum.NACIONAL: config.RATE_NACIONAL,
    }
    return rates[zone]


# ── Lifespan (arranque y apagado) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD al arrancar; libera recursos al apagar."""
    logger.info("Arrancando servicio-envios en puerto %s...", config.PORT)
    init_db()
    yield
    logger.info("Apagando servicio-envios.")


# ── Aplicación FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Servicio de Envíos",
    description="Cotización de tarifas y gestión del ciclo de vida de entregas para el sistema SOA de pedidos.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── Endpoints Públicos ────────────────────────────────────────────────────────
@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Salud"],
    summary="Verificar estado de salud del servicio",
    description="Endpoint público sin autenticación para monitoreo de disponibilidad.",
)
def health_check() -> dict:
    """Retorna el estado de salud y versión del servicio."""
    return {
        "status": "ok",
        "service": "servicio-envios",
        "version": "0.1.0",
        "port": config.PORT,
    }


# ── Endpoints de Zonas y Cotización ───────────────────────────────────────────
@app.get(
    "/zones",
    response_model=List[ZoneInfo],
    tags=["Zonas"],
    summary="Consultar zonas disponibles",
    description="Retorna la lista de zonas de envío soportadas con sus tarifas planas vigentes.",
)
def get_zones(
    _api_key: str = Depends(verify_api_key),
) -> List[dict]:
    """Retorna las zonas de entrega configuradas con sus respectivas tarifas."""
    return [
        {"zone": ZoneEnum.LOCAL.value, "rate": config.RATE_LOCAL},
        {"zone": ZoneEnum.REGIONAL.value, "rate": config.RATE_REGIONAL},
        {"zone": ZoneEnum.NACIONAL.value, "rate": config.RATE_NACIONAL},
    ]


@app.post(
    "/quote",
    response_model=QuoteResponse,
    tags=["Cotización"],
    summary="Cotizar costo de envío por zona",
    description="Calcula la tarifa plana de envío según la zona de destino solicitada.",
)
def quote_shipping(
    quote_in: QuoteRequest,
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """Cotiza el costo de envío para una zona determinada."""
    cost = get_zone_rate(quote_in.zone)
    return {
        "zone": quote_in.zone.value,
        "shipping_cost": cost,
    }


# ── Endpoints de Envíos (CRUD) ─────────────────────────────────────────────────
@app.post(
    "/shipments",
    response_model=ShipmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Envíos"],
    summary="Crear nuevo registro de envío",
    description="Crea un envío para un pedido en estado inicial PENDING con la tarifa vigente de la zona.",
)
def create_shipment(
    shipment_in: ShipmentCreate,
    db: sqlite3.Connection = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """Registra un nuevo envío asociado a un pedido."""
    cursor = db.cursor()
    cursor.execute("SELECT id FROM shipments WHERE order_id = ?;", (shipment_in.order_id,))
    if cursor.fetchone() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un envío registrado para el pedido {shipment_in.order_id}.",
        )

    shipping_cost = get_zone_rate(shipment_in.zone)
    now = datetime.now(UTC).isoformat()
    initial_status = StatusEnum.PENDING.value

    try:
        with db:
            cursor.execute(
                """
                INSERT INTO shipments (order_id, zone, recipient_name, shipping_cost, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    shipment_in.order_id,
                    shipment_in.zone.value,
                    shipment_in.recipient_name,
                    shipping_cost,
                    initial_status,
                    now,
                    now,
                ),
            )
            shipment_id = cursor.lastrowid
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Error de integridad al registrar el envío: {e}",
        )

    cursor.execute("SELECT * FROM shipments WHERE id = ?;", (shipment_id,))
    row = cursor.fetchone()
    return dict(row)


@app.get(
    "/shipments/{id}",
    response_model=ShipmentResponse,
    tags=["Envíos"],
    summary="Consultar envío por ID",
    description="Obtiene el detalle completo y estado actual de un envío.",
)
def get_shipment(
    id: int = Path(..., ge=1, description="Identificador único del envío"),
    db: sqlite3.Connection = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """Consulta un envío por su ID primario."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM shipments WHERE id = ?;", (id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Envío con ID {id} no encontrado.",
        )
    return dict(row)


@app.get(
    "/shipments",
    response_model=ShipmentListResponse,
    tags=["Envíos"],
    summary="Listar envíos con paginación y filtros",
    description="Retorna una lista paginada de envíos con filtros opcionales por status y order_id.",
)
def list_shipments(
    page: int = Query(default=1, ge=1, description="Número de página"),
    page_size: int = Query(default=20, ge=1, le=100, description="Cantidad de registros por página"),
    status_filter: Optional[StatusEnum] = Query(default=None, alias="status", description="Filtrar por estado del envío"),
    order_id: Optional[int] = Query(default=None, ge=1, description="Filtrar por ID de pedido"),
    db: sqlite3.Connection = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """Lista envíos de forma paginada con filtros opcionales por estado y order_id."""
    # Normalizar parámetros por si se invoca la función directamente en pruebas unitarias
    actual_page = page if isinstance(page, int) else 1
    actual_page_size = page_size if isinstance(page_size, int) else 20
    actual_status = status_filter if isinstance(status_filter, StatusEnum) else None
    actual_order_id = order_id if isinstance(order_id, int) else None

    conditions = []
    params = []

    if actual_status is not None:
        conditions.append("status = ?")
        params.append(actual_status.value)

    if actual_order_id is not None:
        conditions.append("order_id = ?")
        params.append(actual_order_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM shipments {where_clause};", params)
    total = cursor.fetchone()[0]

    offset = (actual_page - 1) * actual_page_size
    query = f"""
        SELECT * FROM shipments
        {where_clause}
        ORDER BY id DESC
        LIMIT ? OFFSET ?;
    """
    cursor.execute(query, params + [actual_page_size, offset])
    rows = cursor.fetchall()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": actual_page,
        "page_size": actual_page_size,
    }


@app.patch(
    "/shipments/{id}/status",
    response_model=ShipmentResponse,
    tags=["Envíos"],
    summary="Actualizar estado del envío",
    description="Avanza el estado del envío según las transiciones permitidas por la máquina de estados.",
)
def update_shipment_status(
    id: int = Path(..., ge=1, description="Identificador único del envío"),
    status_in: StatusUpdateRequest = ...,
    db: sqlite3.Connection = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """Actualiza el estado de un envío validando las reglas de la máquina de estados."""
    cursor = db.cursor()
    cursor.execute("SELECT * FROM shipments WHERE id = ?;", (id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Envío con ID {id} no encontrado.",
        )

    current_status = StatusEnum(row["status"])
    new_status = status_in.new_status

    if current_status in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El envío se encuentra en estado terminal '{current_status.value}' y no permite más cambios de estado.",
        )

    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        allowed_str = ", ".join(f"'{s.value}'" for s in allowed) if allowed else "ninguna"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transición no permitida de '{current_status.value}' a '{new_status.value}'. "
                f"Transiciones válidas desde '{current_status.value}': [{allowed_str}]."
            ),
        )

    now = datetime.now(UTC).isoformat()
    with db:
        cursor.execute(
            """
            UPDATE shipments
            SET status = ?, updated_at = ?
            WHERE id = ?;
            """,
            (new_status.value, now, id),
        )

    cursor.execute("SELECT * FROM shipments WHERE id = ?;", (id,))
    updated_row = cursor.fetchone()
    return dict(updated_row)
