"""
Configuración del servicio-envios.
Carga variables de entorno desde el archivo .env en la raíz del proyecto usando find_dotenv().
"""
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Carga el .env raíz subiendo por el árbol de directorios
load_dotenv(find_dotenv(usecwd=False, raise_error_if_not_found=False))

# ── Directorio base del servicio ───────────────────────────────────────────────
SERVICE_DIR: Path = Path(__file__).resolve().parent


class Settings:
    SERVICE_DIR: Path = SERVICE_DIR

    # ── Seguridad ──────────────────────────────────────────────────────────────
    API_KEY: str = os.getenv("API_KEY", "")

    # ── Base de datos ──────────────────────────────────────────────────────────
    _db_filename: str = os.getenv("DB_ENVIOS", "envios.db")
    DB_PATH: Path = SERVICE_DIR / _db_filename

    # ── Servidor ───────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT_ENVIOS", "8003"))
    PORT_ENVIOS: int = PORT

    # ── Tarifas planas de envío ────────────────────────────────────────────────
    RATE_LOCAL: float = float(os.getenv("RATE_LOCAL", "50"))
    RATE_REGIONAL: float = float(os.getenv("RATE_REGIONAL", "100"))
    RATE_NACIONAL: float = float(os.getenv("RATE_NACIONAL", "200"))

    # ── General ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()

# ── Exportaciones a nivel de módulo ───────────────────────────────────────────
API_KEY: str = settings.API_KEY
DB_PATH: Path = settings.DB_PATH
HOST: str = settings.HOST
PORT: int = settings.PORT
PORT_ENVIOS: int = settings.PORT_ENVIOS
RATE_LOCAL: float = settings.RATE_LOCAL
RATE_REGIONAL: float = settings.RATE_REGIONAL
RATE_NACIONAL: float = settings.RATE_NACIONAL
LOG_LEVEL: str = settings.LOG_LEVEL
DEBUG: bool = settings.DEBUG
