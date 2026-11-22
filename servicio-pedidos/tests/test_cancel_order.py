"""
Pruebas para PATCH /orders/{id}/cancel (T-21).
Cubre la cancelación de pedidos activos, máquina de estados con servicio-envios
y liberación de stock en servicio-inventario (RF-6, CF-11, CF-12, CF-13).
"""
from unittest.mock import patch

import pytest
from fastapi import HTTPException

import config
from database import get_connection

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida"


def _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10):
    conn = get_connection(temp_db)
    cursor = conn.cursor()
    with conn:
        cursor.execute(
            """
            INSERT INTO orders (customer_id, customer_name, coverage_zone, shipping_cost,
                                total_amount, status, shipment_id, created_at, updated_at)
            VALUES (1, 'Ana García', 'LOCAL', 50.0, 150.0, ?, ?, '2026-11-22T10:00:00', '2026-11-22T10:00:00');
            """,
            (status, shipment_id),
        )
        order_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal)
            VALUES (?, 5, 'Webcam HD', 100.0, 1, 100.0);
            """,
            (order_id,),
        )
    conn.close()
    return order_id


class TestCancelOrder:
    @patch("clients.get_shipment")
    @patch("clients.cancel_shipment")
    @patch("clients.release_stock")
    def test_cancel_order_success_when_shipment_pending(
        self, mock_rel, mock_cancel_ship, mock_get_ship, client, temp_db
    ):
        """Cancela exitosamente pedido con envío PENDING, liberando stock (CF-11)."""
        order_id = _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10)
        mock_get_ship.return_value = {"id": 10, "status": "PENDING"}
        mock_cancel_ship.return_value = {"id": 10, "status": "CANCELLED"}
        mock_rel.return_value = {"released": [{"product_id": 5, "quantity_released": 1}]}

        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == order_id
        assert data["status"] == "CANCELLED"
        assert data["shipment_status"] == "CANCELLED"

        # Verificar que se llamó a cancelar envío y liberar stock
        mock_cancel_ship.assert_called_once_with(10)
        mock_rel.assert_called_once_with([{"product_id": 5, "quantity": 1}])

        # Verificar actualización en base de datos
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE id = ?;", (order_id,))
        assert cursor.fetchone()["status"] == "CANCELLED"
        conn.close()

    @patch("clients.get_shipment")
    @patch("clients.cancel_shipment")
    @patch("clients.release_stock")
    def test_cancel_order_rejected_when_shipment_in_transit_409(
        self, mock_rel, mock_cancel_ship, mock_get_ship, client, temp_db
    ):
        """Rechaza cancelación con 409 si el envío ya está en tránsito (CF-12)."""
        order_id = _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10)
        mock_get_ship.return_value = {"id": 10, "status": "IN_TRANSIT"}

        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 409
        assert "tránsito o entregado" in resp.json()["detail"]

        # No se tocó el envío ni el stock
        mock_cancel_ship.assert_not_called()
        mock_rel.assert_not_called()

        # El pedido sigue CONFIRMED
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE id = ?;", (order_id,))
        assert cursor.fetchone()["status"] == "CONFIRMED"
        conn.close()

    @patch("clients.get_shipment")
    def test_cancel_order_rejected_when_shipment_delivered_409(self, mock_get_ship, client, temp_db):
        """Rechaza cancelación con 409 si el envío ya fue entregado (CF-12)."""
        order_id = _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10)
        mock_get_ship.return_value = {"id": 10, "status": "DELIVERED"}

        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 409
        assert "tránsito o entregado" in resp.json()["detail"]

    @patch("clients.get_shipment")
    @patch("clients.cancel_shipment")
    @patch("clients.release_stock")
    def test_cancel_order_when_shipment_already_cancelled_omits_call(
        self, mock_rel, mock_cancel_ship, mock_get_ship, client, temp_db
    ):
        """Si el envío ya estaba CANCELLED, omite llamada a envíos, libera stock y cancela pedido (CF-13)."""
        order_id = _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10)
        mock_get_ship.return_value = {"id": 10, "status": "CANCELLED"}
        mock_rel.return_value = {"released": []}

        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"

        # No llama a cancelar el envío porque ya estaba cancelado
        mock_cancel_ship.assert_not_called()
        mock_rel.assert_called_once()

    def test_cancel_order_already_terminal_cancelled_409(self, client, temp_db):
        """Cancelar pedido que ya está CANCELLED responde 409."""
        order_id = _create_order_for_cancel(temp_db, status="CANCELLED")
        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 409
        assert "estado terminal" in resp.json()["detail"]

    def test_cancel_order_already_terminal_failed_409(self, client, temp_db):
        """Cancelar pedido con status=FAILED responde 409."""
        order_id = _create_order_for_cancel(temp_db, status="FAILED")
        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 409
        assert "estado terminal" in resp.json()["detail"]

    @patch("clients.get_shipment")
    def test_cancel_order_shipment_service_down_returns_502(self, mock_get_ship, client, temp_db):
        """Si no se puede consultar el envío porque envíos está caído, responde 502 y pedido queda CONFIRMED."""
        order_id = _create_order_for_cancel(temp_db, status="CONFIRMED", shipment_id=10)
        mock_get_ship.return_value = None

        resp = client.patch(f"/orders/{order_id}/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 502
        assert "servicio de envíos no está disponible" in resp.json()["detail"]

        # Pedido permanece CONFIRMED
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM orders WHERE id = ?;", (order_id,))
        assert cursor.fetchone()["status"] == "CONFIRMED"
        conn.close()

    def test_cancel_order_not_found_404(self, client):
        """Cancelar pedido inexistente responde 404."""
        resp = client.patch("/orders/99999/cancel", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 404
        assert "no encontrado" in resp.json()["detail"].lower()

    def test_cancel_order_auth_missing_401(self, client, temp_db):
        """PATCH /orders/{id}/cancel sin clave responde 401."""
        order_id = _create_order_for_cancel(temp_db)
        resp = client.patch(f"/orders/{order_id}/cancel")
        assert resp.status_code == 401
