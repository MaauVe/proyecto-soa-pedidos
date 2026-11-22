"""
Módulo cliente HTTP para comunicación con los 3 servicios upstream:
- servicio-clientes (8001)
- servicio-inventario (8002)
- servicio-envios (8003)
"""
import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import HTTPException, status

import config

logger = logging.getLogger("servicio-pedidos.clients")


def _get_headers() -> Dict[str, str]:
    return {
        "X-API-Key": config.API_KEY,
        "Content-Type": "application/json",
    }


def validate_customer(customer_id: int) -> Dict[str, Any]:
    """
    Valida un cliente consultando GET /customers/{customer_id}/validate en servicio-clientes.
    Retorna los datos esenciales: id, full_name, coverage_zone, delivery_address, is_active.
    Eleva HTTPException 422 si el cliente no existe (404) o está inactivo (409).
    Eleva HTTPException 503 si hay error de conexión o timeout.
    Eleva HTTPException 502 ante errores 5xx del servicio.
    """
    url = f"{config.URL_CLIENTES}/customers/{customer_id}/validate"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión con servicio-clientes (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de clientes no está disponible.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición con servicio-clientes (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de clientes no está disponible.",
        ) from exc

    if resp.status_code == status.HTTP_200_OK:
        return resp.json()

    if resp.status_code == status.HTTP_404_NOT_FOUND:
        logger.warning("Cliente ID %s no encontrado en servicio-clientes.", customer_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El cliente no fue encontrado.",
        )

    if resp.status_code == status.HTTP_409_CONFLICT:
        logger.warning("Cliente ID %s inactivo en servicio-clientes.", customer_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El cliente existe pero se encuentra inactivo.",
        )

    logger.error("Respuesta inesperada de servicio-clientes: %s - %s", resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Error inesperado devuelto por el servicio de clientes ({resp.status_code}).",
    )


def reserve_stock(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reserva stock atómicamente en servicio-inventario llamando a POST /products/reserve.
    items: [{"product_id": int, "quantity": int}, ...]
    Retorna {"reserved": [{"product_id": ..., "name": ..., "unit_price": ..., "quantity_reserved": ..., ...}]}
    Eleva HTTPException 422 si hay conflicto de stock (409).
    Eleva HTTPException 503 si el servicio no responde.
    Eleva HTTPException 502 si hay error inesperado.
    """
    url = f"{config.URL_INVENTARIO}/products/reserve"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json={"items": items}, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión con servicio-inventario (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de inventario no está disponible.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición con servicio-inventario (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de inventario no está disponible.",
        ) from exc

    if resp.status_code == status.HTTP_200_OK:
        return resp.json()

    if resp.status_code == status.HTTP_409_CONFLICT:
        detail = resp.json().get("detail", "Conflicto al reservar existencias en inventario.")
        logger.warning("Fallo en reserva de inventario: %s", detail)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )

    logger.error("Respuesta inesperada de servicio-inventario: %s - %s", resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Error inesperado devuelto por el servicio de inventario ({resp.status_code}).",
    )


def release_stock(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compensación: Libera stock reservado en servicio-inventario llamando a POST /products/release.
    items: [{"product_id": int, "quantity": int}, ...]
    Retorna {"released": [...]}
    Eleva HTTPException 503/502 si falla.
    """
    url = f"{config.URL_INVENTARIO}/products/release"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json={"items": items}, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión al liberar stock en servicio-inventario (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de inventario no respondió al intentar liberar stock.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición al liberar stock en servicio-inventario (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de inventario no respondió al intentar liberar stock.",
        ) from exc

    if resp.status_code == status.HTTP_200_OK:
        return resp.json()

    logger.error("Error al liberar stock en servicio-inventario: %s - %s", resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Error al liberar stock en inventario ({resp.status_code}): {resp.text}",
    )


def quote_shipment(zone: str) -> float:
    """
    Cotiza el costo de envío consultando POST /quote en servicio-envios.
    Retorna el shipping_cost: float.
    Eleva HTTPException 502 si falla o no está disponible.
    """
    url = f"{config.URL_ENVIOS}/quote"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json={"zone": zone}, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión al cotizar envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de cotización de envíos no está disponible.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición al cotizar envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de cotización de envíos no está disponible.",
        ) from exc

    if resp.status_code == status.HTTP_200_OK:
        data = resp.json()
        return float(data["shipping_cost"])

    logger.error("Error al cotizar envío en servicio-envios: %s - %s", resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="El servicio de cotización de envíos no está disponible.",
    )


def create_shipment(order_id: int, zone: str, recipient_name: str) -> Dict[str, Any]:
    """
    Crea la guía de entrega llamando a POST /shipments en servicio-envios.
    Retorna el diccionario con la información del envío creado (incluyendo 'id').
    Eleva HTTPException 502 si falla la creación.
    """
    url = f"{config.URL_ENVIOS}/shipments"
    payload = {
        "order_id": order_id,
        "zone": zone,
        "recipient_name": recipient_name,
    }
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.post(url, json=payload, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión al crear envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible registrar la guía de envío.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición al crear envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No fue posible registrar la guía de envío.",
        ) from exc

    if resp.status_code == status.HTTP_201_CREATED:
        return resp.json()

    logger.error("Fallo al registrar envío en servicio-envios: %s - %s", resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="No fue posible registrar la guía de envío.",
    )


def get_shipment(shipment_id: int) -> Optional[Dict[str, Any]]:
    """
    Consulta el estado del envío llamando a GET /shipments/{shipment_id} en servicio-envios.
    Retorna el diccionario del envío si es exitoso.
    Retorna None si hay timeout, error de conexión o error HTTP (modo degradado).
    """
    url = f"{config.URL_ENVIOS}/shipments/{shipment_id}"
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.get(url, headers=_get_headers())
        if resp.status_code == status.HTTP_200_OK:
            return resp.json()
        logger.warning("GET /shipments/%s retornó estado %s.", shipment_id, resp.status_code)
        return None
    except Exception as exc:
        logger.warning("No se pudo obtener información del envío %s: %s", shipment_id, exc)
        return None


def cancel_shipment(shipment_id: int) -> Dict[str, Any]:
    """
    Cancela la guía de entrega llamando a PATCH /shipments/{shipment_id}/status en servicio-envios.
    Eleva HTTPException 409 si el estado actual del envío no permite cancelación.
    Eleva HTTPException 502 si falla la conexión o hay error del servicio.
    """
    url = f"{config.URL_ENVIOS}/shipments/{shipment_id}/status"
    payload = {"new_status": "CANCELLED"}
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_SECONDS) as client:
            resp = client.patch(url, json=payload, headers=_get_headers())
    except (httpx.ConnectError, httpx.TimeoutException) as exc:
        logger.error("Error de conexión al cancelar envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de envíos no está disponible.",
        ) from exc
    except httpx.RequestError as exc:
        logger.error("Error de petición al cancelar envío en servicio-envios (%s): %s", url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="El servicio de envíos no está disponible.",
        ) from exc

    if resp.status_code == status.HTTP_200_OK:
        return resp.json()

    if resp.status_code == status.HTTP_409_CONFLICT:
        detail = resp.json().get("detail", "El estado del envío no permite cancelación.")
        logger.warning("Conflicto al cancelar envío %s: %s", shipment_id, detail)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )

    logger.error("Error al cancelar envío %s: %s - %s", shipment_id, resp.status_code, resp.text)
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="El servicio de envíos no está disponible.",
    )
