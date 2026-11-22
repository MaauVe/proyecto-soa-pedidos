"""
Pruebas para GET /orders/{id} (T-19).
Cubre la consulta detallada de pedidos y el enriquecimiento degradado
del estado de envío cuando servicio-envios no responde (RF-4, CF-8, CF-9).
"""
from unittest.mock import patch

import pytest

import config
from database import get_connection

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida"


def _create_sample_order(temp_db, status="CONFIRMED", shipment_id=10, compensation_error=None):
    conn = get_connection(temp_db)
    cursor = conn.cursor()
    with conn:
        cursor.execute(
            """
            INSERT INTO orders (customer_id, customer_name, coverage_zone, shipping_cost,
                                total_amount, status, shipment_id, compensation_error, created_at, updated_at)
            VALUES (1, 'Ana García', 'LOCAL', 50.0, 250.0, ?, ?, ?, '2026-11-22T10:00:00', '2026-11-22T10:00:00');
            """,
            (status, shipment_id, compensation_error),
        )
        order_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal)
            VALUES (?, 1, 'Monitor 4K', 200.0, 1, 200.0);
            """,
            (order_id,),
        )
    conn.close()
    return order_id


class TestGetOrder:
    @patch("clients.get_shipment")
    def test_get_order_success_with_live_shipment(self, mock_get_ship, client, temp_db):
        """GET /orders/{id} retorna el pedido con shipment_status real si servicio-envios responde (CF-9)."""
        order_id = _create_sample_order(temp_db, shipment_id=10)
        mock_get_ship.return_value = {"id": 10, "status": "IN_TRANSIT"}

        resp = client.get(f"/orders/{order_id}", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == order_id
        assert data["customer_name"] == "Ana García"
        assert data["shipment_id"] == 10
        assert data["shipment_status"] == "IN_TRANSIT"
        assert data["shipment_detail"] is None
        assert len(data["items"]) == 1
        assert data["items"][0]["product_name"] == "Monitor 4K"
        mock_get_ship.assert_called_once_with(10)

    @patch("clients.get_shipment")
    def test_get_order_degraded_when_shipment_service_down(self, mock_get_ship, client, temp_db):
        """Si servicio-envios no responde, GET /orders/{id} retorna 200 con shipment_status: null (CF-9)."""
        order_id = _create_sample_order(temp_db, shipment_id=10)
        mock_get_ship.return_value = None  # Simula fallo en servicio-envios

        resp = client.get(f"/orders/{order_id}", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["id"] == order_id
        assert data["shipment_id"] == 10
        assert data["shipment_status"] is None
        assert data["shipment_detail"] == "No disponible temporalmente"

    def test_get_order_without_shipment_id_failed_status(self, client, temp_db):
        """Pedido con status=FAILED y sin shipment_id se retorna completo con shipment_status: null."""
        order_id = _create_sample_order(
            temp_db,
            status="FAILED",
            shipment_id=None,
            compensation_error="Timeout al conectar con inventario",
        )

        resp = client.get(f"/orders/{order_id}", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["status"] == "FAILED"
        assert data["shipment_id"] is None
        assert data["shipment_status"] is None
        assert data["compensation_error"] == "Timeout al conectar con inventario"

    def test_get_order_not_found_404(self, client):
        """Consultar pedido inexistente responde 404 (CF-8)."""
        resp = client.get("/orders/99999", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 404
        assert "no encontrado" in resp.json()["detail"].lower()

    def test_get_order_auth_required_401(self, client, temp_db):
        """GET /orders/{id} sin clave o con clave inválida responde 401."""
        order_id = _create_sample_order(temp_db)
        r1 = client.get(f"/orders/{order_id}")
        assert r1.status_code == 401

        r2 = client.get(f"/orders/{order_id}", headers={"X-API-Key": WRONG_KEY})
        assert r2.status_code == 401
