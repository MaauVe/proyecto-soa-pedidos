"""
Modelos Pydantic para validación y serialización en servicio-inventario.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


# ── Salud del servicio ─────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    service: str = "servicio-inventario"
    version: str = "0.1.0"
    status: str = "ok"
    port: int


# ── Producto: Base y CRUD ──────────────────────────────────────────────────────

class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="Código único de producto (SKU)")
    name: str = Field(..., min_length=1, max_length=200, description="Nombre del producto")
    description: Optional[str] = Field(None, max_length=1000, description="Descripción opcional del producto")
    unit_price: float = Field(..., gt=0, description="Precio unitario (debe ser mayor a cero)")
    weight_kg: float = Field(..., gt=0, description="Peso en kg para cálculo de envío (mayor a cero)")
    stock: int = Field(..., ge=0, description="Existencias disponibles (entero mayor o igual a cero)")

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: str) -> str:
        clean = v.strip().upper()
        if not clean:
            raise ValueError("El SKU no puede estar vacío.")
        return clean

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("El nombre no puede estar vacío.")
        return clean


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: Optional[str] = Field(None, min_length=1, max_length=50)
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    unit_price: Optional[float] = Field(None, gt=0)
    weight_kg: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip().upper()
            if not clean:
                raise ValueError("El SKU no puede estar vacío.")
            return clean
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean = v.strip()
            if not clean:
                raise ValueError("El nombre no puede estar vacío.")
            return clean
        return v


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    unit_price: float
    weight_kg: float
    stock: int
    is_active: bool
    created_at: str
    updated_at: str


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Operaciones de Stock (Reserva, Release, Disponibilidad) ───────────────────

class ReserveItem(BaseModel):
    product_id: int = Field(..., gt=0, description="ID del producto")
    quantity: int = Field(..., gt=0, description="Cantidad a reservar (mínimo 1)")


class ReserveRequest(BaseModel):
    items: List[ReserveItem] = Field(..., min_length=1, description="Lista de productos a reservar")

    @field_validator("items")
    @classmethod
    def validate_unique_products(cls, v: List[ReserveItem]) -> List[ReserveItem]:
        ids = [item.product_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("La lista de reserva contiene product_id duplicados.")
        return v


class ReserveItemResult(BaseModel):
    product_id: int
    name: str
    unit_price: float
    weight_kg: float
    quantity_reserved: int
    stock_remaining: int


class ReserveResponse(BaseModel):
    reserved: List[ReserveItemResult]


class ReleaseItem(BaseModel):
    product_id: int = Field(..., gt=0, description="ID del producto")
    quantity: int = Field(..., gt=0, description="Cantidad a liberar (mínimo 1)")


class ReleaseRequest(BaseModel):
    items: List[ReleaseItem] = Field(..., min_length=1, description="Lista de productos a liberar")

    @field_validator("items")
    @classmethod
    def validate_unique_products(cls, v: List[ReleaseItem]) -> List[ReleaseItem]:
        ids = [item.product_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("La lista de liberación contiene product_id duplicados.")
        return v


class ReleaseItemResult(BaseModel):
    product_id: int
    quantity_released: int
    stock_after: int


class ReleaseResponse(BaseModel):
    released: List[ReleaseItemResult]


class CheckItem(BaseModel):
    product_id: int = Field(..., gt=0, description="ID del producto")
    quantity: int = Field(..., gt=0, description="Cantidad a verificar (mínimo 1)")


class CheckRequest(BaseModel):
    items: List[CheckItem] = Field(..., min_length=1, description="Lista de productos a consultar")

    @field_validator("items")
    @classmethod
    def validate_unique_products(cls, v: List[CheckItem]) -> List[CheckItem]:
        ids = [item.product_id for item in v]
        if len(ids) != len(set(ids)):
            raise ValueError("La lista de consulta contiene product_id duplicados.")
        return v


class CheckItemResult(BaseModel):
    product_id: int
    name: Optional[str] = None
    unit_price: Optional[float] = None
    weight_kg: Optional[float] = None
    available: bool
    stock_current: Optional[int] = None
    quantity_requested: Optional[int] = None
    reason: Optional[str] = None


class CheckResponse(BaseModel):
    all_available: bool
    results: List[CheckItemResult]
