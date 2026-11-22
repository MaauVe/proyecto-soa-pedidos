"""
Configuración del servicio-pedidos (Orquestador).
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
    _db_filename: str = os.getenv("DB_PEDIDOS", "pedidos.db")
    DB_PATH: Path = SERVICE_DIR / _db_filename

    # ── Servidor ───────────────────────────────────────────────────────────────
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT_PEDIDOS", "8004"))
    PORT_PEDIDOS: int = PORT

    # ── URLs de Servicios Upstream ─────────────────────────────────────────────
    URL_CLIENTES: str = os.getenv("URL_CLIENTES", "http://localhost:8001")
    URL_INVENTARIO: str = os.getenv("URL_INVENTARIO", "http://localhost:8002")
    URL_ENVIOS: str = os.getenv("URL_ENVIOS", "http://localhost:8003")
    URL_PEDIDOS: str = os.getenv("URL_PEDIDOS", "http://localhost:8004")

    # ── Timeouts y Resiliencia ─────────────────────────────────────────────────
    HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))

    # ── General ────────────────────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"


settings = Settings()

# ── Exportaciones a nivel de módulo ───────────────────────────────────────────
API_KEY: str = settings.API_KEY
DB_PATH: Path = settings.DB_PATH
HOST: str = settings.HOST
PORT: int = settings.PORT
PORT_PEDIDOS: int = settings.PORT_PEDIDOS
URL_CLIENTES: str = settings.URL_CLIENTES
URL_INVENTARIO: str = settings.URL_INVENTARIO
URL_ENVIOS: str = settings.URL_ENVIOS
URL_PEDIDOS: str = settings.URL_PEDIDOS
HTTP_TIMEOUT_SECONDS: float = settings.HTTP_TIMEOUT_SECONDS
LOG_LEVEL: str = settings.LOG_LEVEL
DEBUG: bool = settings.DEBUG
