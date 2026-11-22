"""
Modelos Pydantic v2 para validación y serialización de datos en servicio-envios.
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ZoneEnum(str, Enum):
    LOCAL = "LOCAL"
    REGIONAL = "REGIONAL"
    NACIONAL = "NACIONAL"


class StatusEnum(str, Enum):
    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


class HealthResponse(BaseModel):
    status: str = Field(..., description="Estado del servicio", examples=["ok"])
    service: str = Field(..., description="Nombre del servicio", examples=["servicio-envios"])
    version: str = Field(..., description="Versión del servicio", examples=["0.1.0"])
    port: int = Field(..., description="Puerto de escucha", examples=[8003])


class ZoneInfo(BaseModel):
    zone: ZoneEnum = Field(..., description="Nombre de la zona de destino")
    rate: float = Field(..., ge=0, description="Tarifa plana de envío para la zona")


class QuoteRequest(BaseModel):
    zone: ZoneEnum = Field(..., description="Zona de destino a cotizar")


class QuoteResponse(BaseModel):
    zone: ZoneEnum = Field(..., description="Zona cotizada")
    shipping_cost: float = Field(..., ge=0, description="Costo de envío calculado")


class ShipmentCreate(BaseModel):
    order_id: int = Field(..., ge=1, description="ID del pedido asociado en servicio-pedidos")
    zone: ZoneEnum = Field(..., description="Zona de destino del envío")
    recipient_name: str = Field(..., min_length=1, description="Nombre del destinatario")

    model_config = ConfigDict(str_strip_whitespace=True)


class StatusUpdateRequest(BaseModel):
    new_status: StatusEnum = Field(..., description="Nuevo estado del envío")


class ShipmentResponse(BaseModel):
    id: int = Field(..., description="Identificador único del envío")
    order_id: int = Field(..., description="ID del pedido asociado")
    zone: ZoneEnum = Field(..., description="Zona de destino")
    recipient_name: str = Field(..., description="Nombre del destinatario")
    shipping_cost: float = Field(..., ge=0, description="Costo del envío")
    status: StatusEnum = Field(..., description="Estado actual del envío")
    created_at: str = Field(..., description="Fecha y hora de creación ISO-8601")
    updated_at: str = Field(..., description="Fecha y hora de última actualización ISO-8601")

    model_config = ConfigDict(from_attributes=True)


class ShipmentListResponse(BaseModel):
    items: List[ShipmentResponse] = Field(..., description="Lista de envíos")
    total: int = Field(..., ge=0, description="Total de envíos encontrados")
    page: int = Field(..., ge=1, description="Número de página actual")
    page_size: int = Field(..., ge=1, description="Tamaño de página")
