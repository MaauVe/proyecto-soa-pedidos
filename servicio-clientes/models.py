"""
Modelo SQLAlchemy para la entidad Customer.
Campos definidos según spec 001-servicio-clientes (aprobada 2026-11-20).
"""
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Retorna la hora actual en UTC (compatible con Python 3.12+)."""
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    """Representa un cliente en el sistema de gestión de pedidos y entregas."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("email", name="uq_customers_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    coverage_zone: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<Customer id={self.id} email={self.email!r} is_active={self.is_active}>"
        )
