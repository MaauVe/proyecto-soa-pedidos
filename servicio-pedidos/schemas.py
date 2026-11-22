"""
Esquemas Pydantic v2 para validación y serialización de datos en servicio-pedidos.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Salud del servicio ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    service: str = Field(default="servicio-pedidos", description="Nombre del servicio")
    status: str = Field(default="ok", description="Estado operativo")
    version: str = Field(default="0.1.0", description="Versión del servicio")
    port: int = Field(default=8004, description="Puerto configurado")

    model_config = ConfigDict(from_attributes=True)
