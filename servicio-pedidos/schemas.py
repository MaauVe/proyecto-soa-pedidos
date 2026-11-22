"""
Esquemas Pydantic v2 para validación y serialización de datos en servicio-pedidos.
"""
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ── Salud del servicio ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    service: str = Field(default="servicio-pedidos", description="Nombre del servicio")
    status: str = Field(default="ok", description="Estado operativo")
    version: str = Field(default="0.1.0", description="Versión del servicio")
    port: int = Field(default=8004, description="Puerto configurado")

    model_config = ConfigDict(from_attributes=True)


# ── Modelos de Creación de Pedido (POST /orders) ────────────────────────────────

class OrderItemIn(BaseModel):
    product_id: int = Field(..., gt=0, description="ID del producto")
    quantity: int = Field(..., gt=0, description="Cantidad a ordenar (mínimo 1)")


class OrderCreate(BaseModel):
    customer_id: int = Field(..., gt=0, description="ID del cliente que realiza el pedido")
    items: List[OrderItemIn] = Field(..., min_length=1, description="Lista de productos a ordenar")

    @field_validator("items")
    @classmethod
    def validate_unique_products(cls, v: List[OrderItemIn]) -> List[OrderItemIn]:
        ids = [item.product_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("La lista de items contiene product_id duplicados.")
        return v


# ── Modelos de Respuesta de Pedido ─────────────────────────────────────────────

class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    product_name: str
    unit_price: float
    quantity: int
    subtotal: float

    model_config = ConfigDict(from_attributes=True)


class OrderResponse(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    coverage_zone: str
    status: str
    shipping_cost: float
    total_amount: float
    shipment_id: Optional[int] = None
    shipment_status: Optional[str] = None
    shipment_detail: Optional[str] = None
    compensation_error: Optional[str] = None
    created_at: str
    updated_at: str
    items: List[OrderItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class OrderSummary(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    coverage_zone: str
    status: str
    total_amount: float
    shipment_id: Optional[int] = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    items: List[OrderSummary]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)
