"""
Servicio de Clientes — Puerto 8001
Gestión del catálogo de clientes del sistema SOA de pedidos y entregas.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import LOG_LEVEL, PORT
from database import init_db

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
async def health_check():
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
