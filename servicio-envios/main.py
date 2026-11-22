"""
Servicio de Envíos — Puerto 8003
Cotización de tarifas y gestión del ciclo de vida de entregas para el sistema SOA.
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
logger = logging.getLogger("servicio-envios")


# ── Lifespan (arranque y apagado) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa la BD al arrancar; libera recursos al apagar."""
    logger.info("Arrancando servicio-envios en puerto %s...", PORT)
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
        "port": PORT,
    }
