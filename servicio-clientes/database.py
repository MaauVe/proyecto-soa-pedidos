"""
Motor de base de datos y gestión de sesiones para servicio-clientes.
Usa SQLAlchemy síncrono con SQLite (clientes.db dentro de servicio-clientes/).
"""
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import DATABASE_URL
from models import Base
from seed import seed_customers

logger = logging.getLogger("servicio-clientes.database")

# ── Motor y fábrica de sesiones ───────────────────────────────────────────────
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # necesario para SQLite + FastAPI
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ── Inicialización ─────────────────────────────────────────────────────────────

def init_db() -> None:
    """
    Crea el esquema de la BD y ejecuta el seed si la tabla está vacía.
    Se llama una vez al arranque del servicio (lifespan de FastAPI).
    """
    logger.info("Inicializando base de datos en: %s", DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_customers(session)
    logger.info("Base de datos lista.")


# ── Dependencia FastAPI ────────────────────────────────────────────────────────

def get_db() -> Session:
    """
    Dependencia de FastAPI: provee una sesión de BD por request
    y garantiza su cierre al terminar (usar con Depends).
    """
    with SessionLocal() as session:
        yield session
