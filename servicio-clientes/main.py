"""
Servicio de Clientes — Puerto 8001
Gestión del catálogo de clientes del sistema SOA de pedidos y entregas.
"""
import logging
import math
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import verify_api_key
from config import LOG_LEVEL, PORT
from database import get_db, init_db
from models import Customer
from schemas import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
)

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=LOG_LEVEL.upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("servicio-clientes")

# ── Lifespan (arranque y apagado) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD y el seed al arrancar; libera recursos al apagar."""
    logger.info("Arrancando servicio-clientes en puerto %s...", PORT)
    init_db()
    yield
    logger.info("Apagando servicio-clientes.")


# ── Aplicación FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="Servicio de Clientes",
    description=(
        "API REST para la gestión del catálogo de clientes. "
        "Permite registrar, consultar, actualizar y desactivar clientes, "
        "y expone un endpoint de validación para otros servicios del sistema SOA."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    tags=["Sistema"],
    summary="Verificación de salud del servicio",
    response_description="Estado operativo del servicio",
)
def health_check():
    """
    Retorna el estado de salud del servicio.
    Este endpoint no requiere autenticación.
    """
    logger.info("Health check solicitado")
    return {
        "service": "servicio-clientes",
        "version": "0.1.0",
        "status": "ok",
        "port": PORT,
    }


@app.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Clientes"],
    summary="Crear un nuevo cliente",
    description="Registra un cliente en el catálogo validando la unicidad del correo electrónico.",
)
def create_customer(
    customer_in: CustomerCreate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Registra un nuevo cliente con estado is_active=true.
    Retorna HTTP 409 si el correo electrónico ya se encuentra registrado.
    """
    # Verificación de unicidad de correo (case-insensitive)
    existing_customer = (
        db.query(Customer)
        .filter(func.lower(Customer.email) == customer_in.email.lower())
        .first()
    )
    if existing_customer:
        logger.warning(
            "Intento de registro con correo duplicado: %s", customer_in.email
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un cliente registrado con ese correo electrónico.",
        )

    new_customer = Customer(
        full_name=customer_in.full_name,
        email=customer_in.email,
        phone=customer_in.phone,
        delivery_address=customer_in.delivery_address,
        coverage_zone=customer_in.coverage_zone,
        is_active=True,
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    logger.info("Cliente creado exitosamente con ID: %s", new_customer.id)
    return new_customer


@app.get(
    "/customers",
    response_model=CustomerListResponse,
    status_code=status.HTTP_200_OK,
    tags=["Clientes"],
    summary="Listado paginado de clientes",
    description="Retorna el listado paginado de clientes con opción de filtrar por estado activo/inactivo.",
)
def list_customers(
    page: int = Query(1, ge=1, description="Número de página (≥ 1)"),
    page_size: int = Query(20, ge=1, le=100, description="Cantidad de elementos por página (1 a 100)"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo (true/false)"),
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Lista clientes con paginación y filtro opcional por estado.
    """
    query = db.query(Customer)
    if is_active is not None:
        query = query.filter(Customer.is_active == is_active)

    total = query.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = (
        query.order_by(Customer.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@app.get(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    tags=["Clientes"],
    summary="Consultar cliente por ID",
    description="Retorna la información completa de un cliente por su identificador único.",
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Consulta un cliente por su ID.
    Retorna HTTP 404 si el cliente no existe.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        logger.warning("Cliente no encontrado con ID: %s", customer_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )
    return customer


@app.patch(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    tags=["Clientes"],
    summary="Actualización parcial de cliente",
    description="Actualiza uno o varios campos de un cliente existente.",
)
def update_customer(
    customer_id: int,
    customer_in: CustomerUpdate,
    db: Session = Depends(get_db),
    _: str = Depends(verify_api_key),
):
    """
    Actualiza parcialmente los datos de un cliente.
    Retorna HTTP 404 si el cliente no existe.
    Retorna HTTP 409 si el correo nuevo ya pertenece a otro cliente.
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        logger.warning("Cliente no encontrado con ID: %s", customer_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cliente no encontrado.",
        )

    update_data = customer_in.model_dump(exclude_unset=True)
    if not update_data:
        return customer

    # Si se actualiza el email, validar que no pertenezca a otro cliente (case-insensitive)
    if "email" in update_data and update_data["email"] is not None:
        new_email = update_data["email"].strip()
        existing_email_customer = (
            db.query(Customer)
            .filter(
                func.lower(Customer.email) == new_email.lower(),
                Customer.id != customer_id,
            )
            .first()
        )
        if existing_email_customer:
            logger.warning(
                "Conflicto de correo al actualizar cliente ID %s: %s",
                customer_id,
                new_email,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un cliente registrado con ese correo electrónico.",
            )

    for field, value in update_data.items():
        setattr(customer, field, value)

    customer.updated_at = datetime.now(UTC).replace(tzinfo=None)
    db.commit()
    db.refresh(customer)
    logger.info("Cliente ID %s actualizado exitosamente.", customer.id)
    return customer