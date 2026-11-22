"""
Dependencia FastAPI para autenticación por X-API-Key.
Todos los endpoints protegidos deben inyectar verify_api_key con Depends().
"""
import logging
from typing import Optional

from fastapi import Header, HTTPException, status

import config

logger = logging.getLogger("servicio-inventario.auth")


def verify_api_key(
    x_api_key: Optional[str] = Header(
        default=None,
        alias="X-API-Key",
        description="Clave de autenticación requerida en todos los endpoints protegidos.",
    ),
) -> str:
    """
    Valida el header X-API-Key contra el valor configurado en variables de entorno.

    - HTTP 401 si el header está ausente o vacío.
    - HTTP 401 si el valor no coincide con API_KEY del entorno.
    - Retorna la clave si es válida.
    """
    if not x_api_key or x_api_key != config.API_KEY:
        logger.warning("Acceso rechazado: API Key inválida o ausente.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida o no proporcionada.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key
