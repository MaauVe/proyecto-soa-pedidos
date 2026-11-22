"""
Servicio Orquestador de Pedidos — Puerto 8004
Coordina la creación, consulta y cancelación de pedidos integrando:
- servicio-clientes (8001)
- servicio-inventario (8002)
- servicio-envios (8003)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, status

import config
from auth import verify_api_key
from database import init_db
from schemas import HealthResponse

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
