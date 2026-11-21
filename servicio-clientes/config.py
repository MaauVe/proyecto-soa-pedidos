"""
Configuración del servicio-clientes.
Carga variables de entorno desde el archivo .env en la raíz del proyecto.
"""
import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

# Busca el .env más cercano subiendo por el árbol de directorios (raíz del proyecto)
load_dotenv(find_dotenv(usecwd=False, raise_error_if_not_found=False))

# ── Seguridad ──────────────────────────────────────────────────────────────────
API_KEY: str = os.getenv("API_KEY", "")

# ── Base de datos ──────────────────────────────────────────────────────────────
# clientes.db vive dentro de servicio-clientes/
_SERVICE_DIR = Path(__file__).parent
_db_filename: str = os.getenv("DB_CLIENTES", "clientes.db")
DATABASE_URL: str = f"sqlite:///{_SERVICE_DIR / _db_filename}"

# ── Servidor ───────────────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT_CLIENTES", "8001"))

# ── General ────────────────────────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
