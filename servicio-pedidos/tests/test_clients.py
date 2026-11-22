"""
Pruebas unitarias para el módulo clients.py (T-17).
Cubre todas las llamadas HTTP a los 3 servicios upstream, timeouts,
errores de conexión y propagación de códigos HTTP (RF-3.1–3.3, RF-3.5–3.6, RF-7, RNF-3, RNF-4).
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

import clients


# ── validate_customer (servicio-clientes) ─────────────────────────────────────

class TestValidateCustomerClient:
    @patch("httpx.Client")
    def test_validate_customer_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": 1,
            "full_name": "Ana García",
            "coverage_zone": "LOCAL",
            "delivery_address": "Av. Principal 123",
            "is_active": True,
        }
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        res = clients.validate_customer(1)
        assert res["full_name"] == "Ana García"
        assert res["coverage_zone"] == "LOCAL"

    @patch("httpx.Client")
    def test_validate_customer_not_found_404(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.validate_customer(999)
        assert exc_info.value.status_code == 422
        assert "no fue encontrado" in exc_info.value.detail

    @patch("httpx.Client")
    def test_validate_customer_inactive_409(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.validate_customer(2)
        assert exc_info.value.status_code == 422
        assert "inactivo" in exc_info.value.detail

    @patch("httpx.Client")
    def test_validate_customer_connect_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("No route to host")

        with pytest.raises(HTTPException) as exc_info:
            clients.validate_customer(1)
        assert exc_info.value.status_code == 503
        assert "no está disponible" in exc_info.value.detail

    @patch("httpx.Client")
    def test_validate_customer_timeout(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException("Read timed out")

        with pytest.raises(HTTPException) as exc_info:
            clients.validate_customer(1)
        assert exc_info.value.status_code == 503
        assert "no está disponible" in exc_info.value.detail

    @patch("httpx.Client")
    def test_validate_customer_server_error_500(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.validate_customer(1)
        assert exc_info.value.status_code == 502


# ── reserve_stock (servicio-inventario) ────────────────────────────────────────

class TestReserveStockClient:
    @patch("httpx.Client")
    def test_reserve_stock_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "reserved": [
                {
                    "product_id": 1,
                    "name": "Teclado Mecánico",
                    "unit_price": 50.0,
                    "quantity_reserved": 2,
                    "stock_remaining": 8,
                }
            ]
        }
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        res = clients.reserve_stock([{"product_id": 1, "quantity": 2}])
        assert len(res["reserved"]) == 1
        assert res["reserved"][0]["product_id"] == 1

    @patch("httpx.Client")
    def test_reserve_stock_conflict_409(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "Stock insuficiente para el producto ID 1."}
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.reserve_stock([{"product_id": 1, "quantity": 100}])
        assert exc_info.value.status_code == 422
        assert "Stock insuficiente" in exc_info.value.detail

    @patch("httpx.Client")
    def test_reserve_stock_connect_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(HTTPException) as exc_info:
            clients.reserve_stock([{"product_id": 1, "quantity": 1}])
        assert exc_info.value.status_code == 503
        assert "inventario no está disponible" in exc_info.value.detail

    @patch("httpx.Client")
    def test_reserve_stock_timeout(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(HTTPException) as exc_info:
            clients.reserve_stock([{"product_id": 1, "quantity": 1}])
        assert exc_info.value.status_code == 503
        assert "inventario no está disponible" in exc_info.value.detail


# ── release_stock (servicio-inventario) ────────────────────────────────────────

class TestReleaseStockClient:
    @patch("httpx.Client")
    def test_release_stock_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "released": [{"product_id": 1, "quantity_released": 2, "stock_after": 10}]
        }
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        res = clients.release_stock([{"product_id": 1, "quantity": 2}])
        assert res["released"][0]["quantity_released"] == 2

    @patch("httpx.Client")
    def test_release_stock_connect_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("Failed")

        with pytest.raises(HTTPException) as exc_info:
            clients.release_stock([{"product_id": 1, "quantity": 2}])
        assert exc_info.value.status_code == 503

    @patch("httpx.Client")
    def test_release_stock_server_error(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal DB error"
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.release_stock([{"product_id": 1, "quantity": 2}])
        assert exc_info.value.status_code == 502


# ── quote_shipment (servicio-envios) ───────────────────────────────────────────

class TestQuoteShipmentClient:
    @patch("httpx.Client")
    def test_quote_shipment_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"zone": "LOCAL", "shipping_cost": 50.0}
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        cost = clients.quote_shipment("LOCAL")
        assert cost == 50.0

    @patch("httpx.Client")
    def test_quote_shipment_connect_error(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.post.side_effect = httpx.ConnectError("Failed")

        with pytest.raises(HTTPException) as exc_info:
            clients.quote_shipment("LOCAL")
        assert exc_info.value.status_code == 502
        assert "cotización de envíos no está disponible" in exc_info.value.detail


# ── create_shipment (servicio-envios) ──────────────────────────────────────────

class TestCreateShipmentClient:
    @patch("httpx.Client")
    def test_create_shipment_success_201(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "id": 12,
            "order_id": 1,
            "zone": "LOCAL",
            "recipient_name": "Ana García",
            "shipping_cost": 50.0,
            "status": "PENDING",
        }
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        res = clients.create_shipment(1, "LOCAL", "Ana García")
        assert res["id"] == 12

    @patch("httpx.Client")
    def test_create_shipment_conflict_or_error(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.text = "Conflict"
        mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.create_shipment(1, "LOCAL", "Ana García")
        assert exc_info.value.status_code == 502
        assert "registrar la guía de envío" in exc_info.value.detail


# ── get_shipment & cancel_shipment (servicio-envios) ───────────────────────────

class TestGetAndCancelShipmentClient:
    @patch("httpx.Client")
    def test_get_shipment_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 12, "status": "PENDING"}
        mock_client_cls.return_value.__enter__.return_value.get.return_value = mock_resp

        res = clients.get_shipment(12)
        assert res is not None
        assert res["status"] == "PENDING"

    @patch("httpx.Client")
    def test_get_shipment_failure_returns_none(self, mock_client_cls):
        mock_client_cls.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError("Down")

        # Modo degradado: no debe elevar excepción sino retornar None
        res = clients.get_shipment(12)
        assert res is None

    @patch("httpx.Client")
    def test_cancel_shipment_success_200(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": 12, "status": "CANCELLED"}
        mock_client_cls.return_value.__enter__.return_value.patch.return_value = mock_resp

        res = clients.cancel_shipment(12)
        assert res["status"] == "CANCELLED"

    @patch("httpx.Client")
    def test_cancel_shipment_conflict_409(self, mock_client_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 409
        mock_resp.json.return_value = {"detail": "El envío se encuentra en estado terminal."}
        mock_client_cls.return_value.__enter__.return_value.patch.return_value = mock_resp

        with pytest.raises(HTTPException) as exc_info:
            clients.cancel_shipment(12)
        assert exc_info.value.status_code == 409
