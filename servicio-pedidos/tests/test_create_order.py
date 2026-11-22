"""
Pruebas para POST /orders (T-18).
Cubre el flujo de orquestación de 5 pasos, validaciones Pydantic, y la Saga de compensación
ante fallos en cotización, BD o creación de envío (RF-3 completo, CF-3 a CF-7).
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

import config
from database import get_connection

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida"


@pytest.fixture
def mock_upstream():
    """Mockea los 3 servicios upstream con respuestas exitosas por defecto."""
    with patch("clients.validate_customer") as mock_val, \
         patch("clients.reserve_stock") as mock_res, \
         patch("clients.release_stock") as mock_rel, \
         patch("clients.quote_shipment") as mock_quote, \
         patch("clients.create_shipment") as mock_ship:

        mock_val.return_value = {
            "id": 1,
            "full_name": "Ana García",
            "coverage_zone": "LOCAL",
            "delivery_address": "Av. Central 456",
            "is_active": True,
        }
        mock_res.return_value = {
            "reserved": [
                {
                    "product_id": 10,
                    "name": "Teclado RGB",
                    "unit_price": 100.0,
                    "quantity_reserved": 2,
                    "stock_remaining": 8,
                },
                {
                    "product_id": 20,
                    "name": "Mouse Gamer",
                    "unit_price": 50.0,
                    "quantity_reserved": 1,
                    "stock_remaining": 4,
                },
            ]
        }
        mock_rel.return_value = {"released": []}
        mock_quote.return_value = 50.0  # shipping_cost
        mock_ship.return_value = {"id": 88, "status": "PENDING"}

        yield {
            "val": mock_val,
            "res": mock_res,
            "rel": mock_rel,
            "quote": mock_quote,
            "ship": mock_ship,
        }


class TestCreateOrderSuccess:
    def test_create_order_success_complete_flow(self, client, mock_upstream, temp_db):
        """Flujo exitoso completo de 5 pasos: 201 Created y pedido CONFIRMED (CF-3)."""
        payload = {
            "customer_id": 1,
            "items": [
                {"product_id": 10, "quantity": 2},
                {"product_id": 20, "quantity": 1},
            ],
        }
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 201
        data = resp.json()

        assert data["id"] > 0
        assert data["customer_id"] == 1
        assert data["customer_name"] == "Ana García"
        assert data["coverage_zone"] == "LOCAL"
        assert data["status"] == "CONFIRMED"
        assert data["shipping_cost"] == 50.0
        # (100 * 2) + (50 * 1) + 50 = 300.0
        assert data["total_amount"] == 300.0
        assert data["shipment_id"] == 88
        assert data["shipment_status"] == "PENDING"
        assert data["shipment_detail"] is None
        assert data["compensation_error"] is None
        assert len(data["items"]) == 2

        # Verificar persistencia en base de datos
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status, shipment_id FROM orders WHERE id = ?;", (data["id"],))
        order_row = cursor.fetchone()
        assert order_row["status"] == "CONFIRMED"
        assert order_row["shipment_id"] == 88

        cursor.execute("SELECT COUNT(*) AS c FROM order_items WHERE order_id = ?;", (data["id"],))
        assert cursor.fetchone()["c"] == 2
        conn.close()

        # Verificar que compensación nunca fue llamada
        mock_upstream["rel"].assert_not_called()


class TestCreateOrderValidationErrors:
    def test_customer_not_found_propagates_422(self, client, mock_upstream):
        """Si el cliente no existe, validate_customer eleva 422 y no se reserva stock (CF-4)."""
        mock_upstream["val"].side_effect = HTTPException(status_code=422, detail="El cliente no fue encontrado.")

        payload = {"customer_id": 999, "items": [{"product_id": 1, "quantity": 1}]}
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 422
        assert "no fue encontrado" in resp.json()["detail"]
        mock_upstream["res"].assert_not_called()

    def test_customer_inactive_propagates_422(self, client, mock_upstream):
        """Si el cliente está inactivo, responde 422 y no se reserva stock (CF-4)."""
        mock_upstream["val"].side_effect = HTTPException(status_code=422, detail="El cliente existe pero se encuentra inactivo.")

        payload = {"customer_id": 2, "items": [{"product_id": 1, "quantity": 1}]}
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 422
        assert "inactivo" in resp.json()["detail"]
        mock_upstream["res"].assert_not_called()

    def test_insufficient_stock_propagates_422(self, client, mock_upstream, temp_db):
        """Si no hay stock suficiente, responde 422 y no crea pedidos en BD (CF-5)."""
        mock_upstream["res"].side_effect = HTTPException(status_code=422, detail="Stock insuficiente para el producto ID 10.")

        payload = {"customer_id": 1, "items": [{"product_id": 10, "quantity": 999}]}
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 422
        assert "Stock insuficiente" in resp.json()["detail"]
        mock_upstream["rel"].assert_not_called()

        # BD vacía
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM orders;")
        assert cursor.fetchone()["c"] == 0
        conn.close()

    def test_empty_items_list_rejected_422(self, client):
        """Body con lista items vacía debe responder 422."""
        payload = {"customer_id": 1, "items": []}
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 422

    def test_duplicate_product_ids_rejected_422(self, client):
        """Body con product_id duplicados debe responder 422."""
        payload = {
            "customer_id": 1,
            "items": [
                {"product_id": 5, "quantity": 1},
                {"product_id": 5, "quantity": 2},
            ],
        }
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 422
        assert "duplicados" in resp.text

    def test_invalid_customer_id_or_quantity_422(self, client):
        """customer_id <= 0 o quantity <= 0 responden 422."""
        resp1 = client.post("/orders", json={"customer_id": 0, "items": [{"product_id": 1, "quantity": 1}]}, headers={"X-API-Key": VALID_KEY})
        assert resp1.status_code == 422

        resp2 = client.post("/orders", json={"customer_id": 1, "items": [{"product_id": 1, "quantity": 0}]}, headers={"X-API-Key": VALID_KEY})
        assert resp2.status_code == 422

    def test_missing_and_invalid_api_key_401(self, client):
        """POST /orders sin X-API-Key o con clave inválida responde 401."""
        payload = {"customer_id": 1, "items": [{"product_id": 1, "quantity": 1}]}
        r1 = client.post("/orders", json=payload)
        assert r1.status_code == 401

        r2 = client.post("/orders", json=payload, headers={"X-API-Key": WRONG_KEY})
        assert r2.status_code == 401


class TestCreateOrderCompensationSaga:
    def test_quote_fails_compensates_stock_and_returns_502(self, client, mock_upstream, temp_db):
        """Si falla la cotización, libera el stock reservado y responde 502 (CF-6)."""
        mock_upstream["quote"].side_effect = HTTPException(status_code=502, detail="El servicio de cotización de envíos no está disponible.")

        payload = {
            "customer_id": 1,
            "items": [
                {"product_id": 10, "quantity": 2},
                {"product_id": 20, "quantity": 1},
            ],
        }
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 502
        assert "cotización de envíos" in resp.json()["detail"]

        # Se llamó a la liberación de stock con los productos reservados
        mock_upstream["rel"].assert_called_once()
        released_args = mock_upstream["rel"].call_args[0][0]
        assert released_args == [
            {"product_id": 10, "quantity": 2},
            {"product_id": 20, "quantity": 1},
        ]

        # Ningún pedido persistido
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM orders;")
        assert cursor.fetchone()["c"] == 0
        conn.close()

    def test_shipment_fails_compensates_stock_deletes_order_and_returns_502(self, client, mock_upstream, temp_db):
        """Si falla el registro de envío, libera stock, elimina el pedido local y responde 502 (CF-6)."""
        mock_upstream["ship"].side_effect = HTTPException(status_code=502, detail="No fue posible registrar la guía de envío.")

        payload = {
            "customer_id": 1,
            "items": [
                {"product_id": 10, "quantity": 2},
                {"product_id": 20, "quantity": 1},
            ],
        }
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 502
        assert "registrar la guía de envío" in resp.json()["detail"]

        # Se ejecutó compensación de stock
        mock_upstream["rel"].assert_called_once()

        # El pedido fue limpiado de la base de datos para no dejar registros inconsistentes
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM orders;")
        assert cursor.fetchone()["c"] == 0
        cursor.execute("SELECT COUNT(*) AS c FROM order_items;")
        assert cursor.fetchone()["c"] == 0
        conn.close()

    def test_shipment_fails_and_compensation_fails_sets_failed_order_500(self, client, mock_upstream, temp_db):
        """Si falla el envío Y la compensación también falla, guarda status=FAILED y responde 500 (CF-7)."""
        mock_upstream["ship"].side_effect = HTTPException(status_code=502, detail="Servicio de envíos caído.")
        mock_upstream["rel"].side_effect = RuntimeError("Servicio de inventario no disponible para release.")

        payload = {
            "customer_id": 1,
            "items": [
                {"product_id": 10, "quantity": 2},
                {"product_id": 20, "quantity": 1},
            ],
        }
        resp = client.post("/orders", json=payload, headers={"X-API-Key": VALID_KEY})

        assert resp.status_code == 500
        assert "intervención manual" in resp.json()["detail"]

        # Pedido debe existir en BD con estado FAILED y error de compensación documentado
        conn = get_connection(temp_db)
        cursor = conn.cursor()
        cursor.execute("SELECT status, compensation_error FROM orders;")
        row = cursor.fetchone()
        assert row is not None
        assert row["status"] == "FAILED"
        assert "Servicio de inventario no disponible" in row["compensation_error"]
        conn.close()
