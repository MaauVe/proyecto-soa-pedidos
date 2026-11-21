"""
Esquemas Pydantic para el servicio-clientes.
Definidos según la especificación specs/001-servicio-clientes/spec.md (RF-2, RF-3, etc.).
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CustomerBase(BaseModel):
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Nombre completo del cliente",
    )
    email: str = Field(
        ...,
        max_length=255,
        description="Correo electrónico del cliente",
    )
    phone: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Teléfono de contacto",
    )
    delivery_address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Dirección de entrega",
    )
    coverage_zone: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Zona de cobertura (ej. Local, Regional, Nacional)",
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip()
        if "@" not in clean or clean.startswith("@") or clean.endswith("@"):
            raise ValueError("El correo electrónico debe ser válido y contener '@'.")
        return clean

    @field_validator("full_name", "phone", "delivery_address", "coverage_zone")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("El campo no puede estar vacío.")
        return clean


class CustomerCreate(CustomerBase):
    """Esquema para la creación de un nuevo cliente."""
    pass


class CustomerResponse(CustomerBase):
    """Esquema de respuesta completa para un cliente."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
