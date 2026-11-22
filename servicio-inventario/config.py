"""
Configuración del servicio-inventario.
Carga variables de entorno desde el archivo .env en la raíz del proyecto usando find_dotenv().
"""
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Carga el .env raíz subiendo por el árbol de directorios
load_dotenv(find_dotenv(usecwd=False, raise_error_if_not_found=False))

# ── Directorio base del servicio ───────────────────────────────────────────────
SERVICE_DIR: Path = Path(__file__).resolve().parent

# ── Seguridad ──────────────────────────────────────────────────────────────────
API_KEY: str = os.getenv("API_KEY", "")

# ── Base de datos ──────────────────────────────────────────────────────────────
# inventario.db vive dentro de servicio-inventario/
_db_filename: str = os.getenv("DB_INVENTARIO", "inventario.db")
DB_PATH: Path = SERVICE_DIR / _db_filename

# ── Servidor ───────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT_INVENTARIO", "8002"))

# ── General ────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
