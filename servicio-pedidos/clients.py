"""
Módulo cliente HTTP para comunicación con los 3 servicios upstream:
- servicio-clientes (8001)
- servicio-inventario (8002)
- servicio-envios (8003)

Stub inicial para T-14; la implementación completa se realizará en T-17.
"""
from typing import Any, Dict, List, Optional


def validate_customer(customer_id: int) -> Dict[str, Any]:
    """Stub: Validará el cliente contra servicio-clientes (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def reserve_stock(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Stub: Reservará stock en servicio-inventario (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def release_stock(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Stub: Liberará stock en servicio-inventario (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def quote_shipment(zone: str) -> float:
    """Stub: Cotizará costo de envío en servicio-envios (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def create_shipment(order_id: int, zone: str, recipient_name: str) -> Dict[str, Any]:
    """Stub: Registrará envío en servicio-envios (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def get_shipment(shipment_id: int) -> Optional[Dict[str, Any]]:
    """Stub: Consultará estado de envío en servicio-envios (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")


def cancel_shipment(shipment_id: int) -> Dict[str, Any]:
    """Stub: Cancelará envío en servicio-envios (T-17)."""
    raise NotImplementedError("Se implementará en T-17.")
