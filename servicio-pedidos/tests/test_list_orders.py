"""
Pruebas para GET /orders (T-20).
Cubre el listado paginado de pedidos y filtros por status y customer_id (RF-5, CF-10).
"""
import pytest

import config
from database import get_connection

VALID_KEY = config.API_KEY
WRONG_KEY = "clave-invalida"


def _seed_orders_for_listing(temp_db):
    conn = get_connection(temp_db)
    cursor = conn.cursor()
    with conn:
        cursor.execute(
            """
            INSERT INTO orders (customer_id, customer_name, coverage_zone, shipping_cost,
                                total_amount, status, shipment_id, created_at, updated_at)
            VALUES
                (1, 'Cliente Uno', 'LOCAL', 50.0, 150.0, 'CONFIRMED', 101, '2026-11-22T08:00:00', '2026-11-22T08:00:00'),
                (1, 'Cliente Uno', 'LOCAL', 50.0, 200.0, 'CANCELLED', 102, '2026-11-22T09:00:00', '2026-11-22T09:00:00'),
                (2, 'Cliente Dos', 'REGIONAL', 100.0, 300.0, 'CONFIRMED', 103, '2026-11-22T10:00:00', '2026-11-22T10:00:00');
            """
        )
    conn.close()


class TestListOrders:
    def test_list_orders_default_pagination(self, client, temp_db):
        """GET /orders sin query params lista todos los pedidos con paginación por defecto (CF-10)."""
        _seed_orders_for_listing(temp_db)

        resp = client.get("/orders", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 3
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 1
        assert len(data["items"]) == 3

    def test_list_orders_filter_by_status(self, client, temp_db):
        """Filtro ?status=CONFIRMED retorna solo los pedidos confirmados."""
        _seed_orders_for_listing(temp_db)

        resp = client.get("/orders?status=CONFIRMED", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 2
        for it in data["items"]:
            assert it["status"] == "CONFIRMED"

    def test_list_orders_filter_by_customer_id(self, client, temp_db):
        """Filtro ?customer_id=2 retorna solo los pedidos de ese cliente."""
        _seed_orders_for_listing(temp_db)

        resp = client.get("/orders?customer_id=2", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 1
        assert data["items"][0]["customer_id"] == 2

    def test_list_orders_empty_db(self, client):
        """BD vacía retorna total: 0 y lista de items vacía."""
        resp = client.get("/orders", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["total_pages"] == 0

    def test_list_orders_page_beyond_total(self, client, temp_db):
        """page mayor al total retorna items: [] sin error."""
        _seed_orders_for_listing(temp_db)

        resp = client.get("/orders?page=99", headers={"X-API-Key": VALID_KEY})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["items"] == []

    def test_list_orders_invalid_page_size_422(self, client):
        """page_size menor a 1 o mayor a 100 responde 422."""
        r1 = client.get("/orders?page_size=0", headers={"X-API-Key": VALID_KEY})
        assert r1.status_code == 422

        r2 = client.get("/orders?page_size=101", headers={"X-API-Key": VALID_KEY})
        assert r2.status_code == 422

    def test_list_orders_auth_missing_401(self, client):
        """GET /orders sin autenticación responde 401."""
        resp = client.get("/orders")
        assert resp.status_code == 401
