"""
Servicio de Catálogo e Inventario — Puerto 8002
Gestión de productos y existencias para el sistema SOA de pedidos y entregas.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import LOG_LEVEL, PORT
from database import init_db
from schemas import HealthResponse

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
