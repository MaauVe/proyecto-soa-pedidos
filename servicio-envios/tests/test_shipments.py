"""
Tests consolidados para T-08 a T-12 (Bloque 2 y 3) — servicio-envios.
Cubre la creación, consulta, listado y máquina de estados de envíos:
- T-08: POST /shipments — Creación de envíos y validaciones (RF-5).
- T-09: GET /shipments/{id} — Consulta por ID (RF-6).
- T-10: GET /shipments — Listado paginado y filtros por status y order_id (RF-7).
- T-11: PATCH /shipments/{id}/status — Máquina de estados y transiciones (RF-8).
- T-12: Casos límite y validaciones adicionales.
"""
import inspect
import sqlite3
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from auth import verify_api_key
from database import get_connection
from main import app, create_shipment, get_shipment, list_shipments, update_shipment_status
from schemas import ShipmentCreate, StatusEnum, StatusUpdateRequest, ZoneEnum

DUMMY_KEY = "test-key"


def _route_requires_auth(path: str, method: str) -> bool:
    """Verifica si una ruta y método de FastAPI exigen la dependencia verify_api_key."""
    route = next((r for r in app.routes if getattr(r, "path", None) == path and method in getattr(r, "methods", [])), None)
    if not route:
        return False
    param_deps = [
        param.default.dependency
        for param in inspect.signature(route.endpoint).parameters.values()
        if hasattr(param.default, "dependency")
    ]
    dep_callables = [d.dependency for d in getattr(route, "dependencies", [])]
    return verify_api_key in (param_deps + dep_callables)


@pytest.fixture
def db_conn(tmp_path):
    """Crea una base de datos temporal con el esquema de envios."""
    from database import init_db
    db_file = tmp_path / "test_shipments.db"
    init_db(db_file)
    conn = get_connection(db_file)
    try:
        yield conn
    finally:
        conn.close()


# ── T-08: POST /shipments ─────────────────────────────────────────────────────

class TestCreateShipment:
    def test_create_shipment_route_requires_auth(self):
        """POST /shipments exige verify_api_key."""
        assert _route_requires_auth("/shipments", "POST")

    def test_create_shipment_success(self, db_conn):
        """Crear un envío con datos válidos retorna el envío con status PENDING y costo correspondiente."""
        payload = ShipmentCreate(
            order_id=101,
            zone=ZoneEnum.LOCAL,
            recipient_name="Carlos Santana",
        )
        result = create_shipment(shipment_in=payload, db=db_conn, _api_key=DUMMY_KEY)

        assert result["id"] is not None
        assert result["order_id"] == 101
        assert result["zone"] == "LOCAL"
        assert result["recipient_name"] == "Carlos Santana"
        assert result["shipping_cost"] == 50.0
        assert result["status"] == "PENDING"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    def test_create_shipment_duplicate_order_id_raises_409(self, db_conn):
        """Intentar crear un envío con un order_id ya registrado lanza HTTPException 409."""
        payload1 = ShipmentCreate(
            order_id=102,
            zone=ZoneEnum.LOCAL,
            recipient_name="Ana Garcia",
        )
        create_shipment(shipment_in=payload1, db=db_conn, _api_key=DUMMY_KEY)

        payload2 = ShipmentCreate(
            order_id=102,
            zone=ZoneEnum.REGIONAL,
            recipient_name="Ana Garcia Repetida",
        )
        with pytest.raises(HTTPException) as exc_info:
            create_shipment(shipment_in=payload2, db=db_conn, _api_key=DUMMY_KEY)

        assert exc_info.value.status_code == 409
        assert "102" in exc_info.value.detail
        assert "Ya existe un envío registrado" in exc_info.value.detail

    def test_create_shipment_regional_and_nacional_tariffs(self, db_conn):
        """Las zonas REGIONAL y NACIONAL reciben sus tarifas respectivas."""
        ship_reg = create_shipment(
            shipment_in=ShipmentCreate(order_id=201, zone=ZoneEnum.REGIONAL, recipient_name="Cliente Regional"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert ship_reg["shipping_cost"] == 100.0

        ship_nac = create_shipment(
            shipment_in=ShipmentCreate(order_id=202, zone=ZoneEnum.NACIONAL, recipient_name="Cliente Nacional"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert ship_nac["shipping_cost"] == 200.0

    def test_create_shipment_invalid_zone_raises_validation_error(self):
        """Zona no soportada lanza ValidationError."""
        with pytest.raises(ValidationError):
            ShipmentCreate(order_id=301, zone="INTERNACIONAL", recipient_name="Valente")

    def test_create_shipment_empty_recipient_raises_validation_error(self):
        """Nombre de destinatario vacío lanza ValidationError."""
        with pytest.raises(ValidationError):
            ShipmentCreate(order_id=302, zone=ZoneEnum.LOCAL, recipient_name="")

    def test_create_shipment_whitespace_recipient_raises_validation_error(self):
        """Nombre de destinatario con solo espacios en blanco lanza ValidationError."""
        with pytest.raises(ValidationError):
            ShipmentCreate(order_id=303, zone=ZoneEnum.LOCAL, recipient_name="     ")

    def test_create_shipment_invalid_order_id_raises_validation_error(self):
        """order_id menor a 1 lanza ValidationError."""
        with pytest.raises(ValidationError):
            ShipmentCreate(order_id=0, zone=ZoneEnum.LOCAL, recipient_name="Valente")


# ── T-09: GET /shipments/{id} ─────────────────────────────────────────────────

class TestGetShipment:
    def test_get_shipment_route_requires_auth(self):
        """GET /shipments/{id} exige verify_api_key."""
        assert _route_requires_auth("/shipments/{id}", "GET")

    def test_get_shipment_success(self, db_conn):
        """Consultar un envío por ID retorna el detalle completo con los 8 campos."""
        created = create_shipment(
            shipment_in=ShipmentCreate(order_id=401, zone=ZoneEnum.LOCAL, recipient_name="Mario Bros"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = created["id"]

        result = get_shipment(id=shipment_id, db=db_conn, _api_key=DUMMY_KEY)
        assert result["id"] == shipment_id
        assert result["order_id"] == 401
        assert result["zone"] == "LOCAL"
        assert result["recipient_name"] == "Mario Bros"
        assert result["shipping_cost"] == 50.0
        assert result["status"] == "PENDING"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    def test_get_shipment_not_found_raises_404(self, db_conn):
        """Consultar un ID inexistente lanza HTTPException 404 en español."""
        with pytest.raises(HTTPException) as exc_info:
            get_shipment(id=99999, db=db_conn, _api_key=DUMMY_KEY)

        assert exc_info.value.status_code == 404
        assert "no encontrado" in exc_info.value.detail.lower()


# ── T-10: GET /shipments ──────────────────────────────────────────────────────

class TestListShipments:
    def test_list_shipments_route_requires_auth(self):
        """GET /shipments exige verify_api_key."""
        assert _route_requires_auth("/shipments", "GET")

    def test_list_shipments_empty_db(self, db_conn):
        """Listar envíos en una BD vacía retorna items vacíos y total 0."""
        result = list_shipments(db=db_conn, _api_key=DUMMY_KEY)
        assert result["items"] == []
        assert result["total"] == 0
        assert result["page"] == 1
        assert result["page_size"] == 20

    def test_list_shipments_multiple_records(self, db_conn):
        """Listar envíos retorna todos los registros insertados."""
        for i in range(1, 4):
            create_shipment(
                shipment_in=ShipmentCreate(order_id=500 + i, zone=ZoneEnum.LOCAL, recipient_name=f"Destinatario {i}"),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        result = list_shipments(db=db_conn, _api_key=DUMMY_KEY)
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_list_shipments_filter_by_status(self, db_conn):
        """Filtrar por status retorna únicamente los envíos que coinciden con dicho estado."""
        create_shipment(
            shipment_in=ShipmentCreate(order_id=601, zone=ZoneEnum.LOCAL, recipient_name="Pendiente 1"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        create_shipment(
            shipment_in=ShipmentCreate(order_id=602, zone=ZoneEnum.LOCAL, recipient_name="Pendiente 2"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )

        result = list_shipments(status_filter=StatusEnum.PENDING, db=db_conn, _api_key=DUMMY_KEY)
        assert result["total"] == 2
        for item in result["items"]:
            assert item["status"] == "PENDING"

        # Filtrar por un estado sin registros retorna total 0
        result_empty = list_shipments(status_filter=StatusEnum.DELIVERED, db=db_conn, _api_key=DUMMY_KEY)
        assert result_empty["total"] == 0
        assert result_empty["items"] == []

    def test_list_shipments_filter_by_order_id(self, db_conn):
        """Filtrar por order_id retorna exclusivamente el envío correspondiente a dicho pedido."""
        create_shipment(
            shipment_in=ShipmentCreate(order_id=701, zone=ZoneEnum.LOCAL, recipient_name="Pedido 701"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        create_shipment(
            shipment_in=ShipmentCreate(order_id=702, zone=ZoneEnum.REGIONAL, recipient_name="Pedido 702"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )

        result = list_shipments(order_id=701, db=db_conn, _api_key=DUMMY_KEY)
        assert result["total"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["order_id"] == 701

    def test_list_shipments_pagination(self, db_conn):
        """La paginación funciona correctamente dividiendo en páginas con page y page_size."""
        for i in range(1, 6):
            create_shipment(
                shipment_in=ShipmentCreate(order_id=800 + i, zone=ZoneEnum.LOCAL, recipient_name=f"Paginado {i}"),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        # Página 1 con tamaño 3 -> 3 registros
        p1 = list_shipments(page=1, page_size=3, db=db_conn, _api_key=DUMMY_KEY)
        assert p1["total"] == 5
        assert len(p1["items"]) == 3
        assert p1["page"] == 1
        assert p1["page_size"] == 3

        # Página 2 con tamaño 3 -> 2 registros restantes
        p2 = list_shipments(page=2, page_size=3, db=db_conn, _api_key=DUMMY_KEY)
        assert p2["total"] == 5
        assert len(p2["items"]) == 2
        assert p2["page"] == 2
        assert p2["page_size"] == 3


# ── T-11: PATCH /shipments/{id}/status ────────────────────────────────────────

class TestUpdateShipmentStatus:
    def test_update_status_route_requires_auth(self):
        """PATCH /shipments/{id}/status exige verify_api_key."""
        assert _route_requires_auth("/shipments/{id}/status", "PATCH")

    def test_update_status_pending_to_in_transit_success(self, db_conn):
        """Transición válida: PENDING -> IN_TRANSIT actualiza el estado a 200 OK."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1001, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1001"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]

        update_req = StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT)
        result = update_shipment_status(id=shipment_id, status_in=update_req, db=db_conn, _api_key=DUMMY_KEY)

        assert result["id"] == shipment_id
        assert result["status"] == "IN_TRANSIT"
        assert result["updated_at"] is not None

    def test_update_status_in_transit_to_delivered_success(self, db_conn):
        """Transición válida: PENDING -> IN_TRANSIT -> DELIVERED."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1002, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1002"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]

        # Avanzar a IN_TRANSIT
        update_shipment_status(
            id=shipment_id,
            status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )

        # Avanzar a DELIVERED
        result = update_shipment_status(
            id=shipment_id,
            status_in=StatusUpdateRequest(new_status=StatusEnum.DELIVERED),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert result["status"] == "DELIVERED"

    def test_update_status_pending_to_cancelled_success(self, db_conn):
        """Transición válida: PENDING -> CANCELLED."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1003, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1003"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        result = update_shipment_status(
            id=shipment["id"],
            status_in=StatusUpdateRequest(new_status=StatusEnum.CANCELLED),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert result["status"] == "CANCELLED"

    def test_update_status_in_transit_to_cancelled_success(self, db_conn):
        """Transición válida: IN_TRANSIT -> CANCELLED."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1004, zone=ZoneEnum.REGIONAL, recipient_name="Destinatario 1004"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]

        update_shipment_status(
            id=shipment_id,
            status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )

        result = update_shipment_status(
            id=shipment_id,
            status_in=StatusUpdateRequest(new_status=StatusEnum.CANCELLED),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert result["status"] == "CANCELLED"

    def test_update_status_pending_to_delivered_invalid_raises_409(self, db_conn):
        """Transición inválida: PENDING -> DELIVERED (sin pasar por IN_TRANSIT) lanza HTTPException 409."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1005, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1005"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        with pytest.raises(HTTPException) as exc_info:
            update_shipment_status(
                id=shipment["id"],
                status_in=StatusUpdateRequest(new_status=StatusEnum.DELIVERED),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        assert exc_info.value.status_code == 409
        assert "Transición no permitida" in exc_info.value.detail
        assert "PENDING" in exc_info.value.detail
        assert "DELIVERED" in exc_info.value.detail

    def test_update_status_same_status_raises_409(self, db_conn):
        """Intentar actualizar al mismo estado actual lanza HTTPException 409."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1006, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1006"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        with pytest.raises(HTTPException) as exc_info:
            update_shipment_status(
                id=shipment["id"],
                status_in=StatusUpdateRequest(new_status=StatusEnum.PENDING),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        assert exc_info.value.status_code == 409
        assert "Transición no permitida" in exc_info.value.detail

    def test_update_status_from_delivered_terminal_raises_409(self, db_conn):
        """Envío en estado DELIVERED (terminal) rechaza cualquier cambio con HTTPException 409."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1007, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1007"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]
        update_shipment_status(id=shipment_id, status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT), db=db_conn, _api_key=DUMMY_KEY)
        update_shipment_status(id=shipment_id, status_in=StatusUpdateRequest(new_status=StatusEnum.DELIVERED), db=db_conn, _api_key=DUMMY_KEY)

        with pytest.raises(HTTPException) as exc_info:
            update_shipment_status(
                id=shipment_id,
                status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        assert exc_info.value.status_code == 409
        assert "estado terminal" in exc_info.value.detail.lower()

    def test_update_status_from_cancelled_terminal_raises_409(self, db_conn):
        """Envío en estado CANCELLED (terminal) rechaza cualquier cambio con HTTPException 409."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1008, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1008"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]
        update_shipment_status(id=shipment_id, status_in=StatusUpdateRequest(new_status=StatusEnum.CANCELLED), db=db_conn, _api_key=DUMMY_KEY)

        with pytest.raises(HTTPException) as exc_info:
            update_shipment_status(
                id=shipment_id,
                status_in=StatusUpdateRequest(new_status=StatusEnum.PENDING),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        assert exc_info.value.status_code == 409
        assert "estado terminal" in exc_info.value.detail.lower()

    def test_update_status_non_existent_id_raises_404(self, db_conn):
        """Actualizar el estado de un envío con ID inexistente lanza HTTPException 404."""
        with pytest.raises(HTTPException) as exc_info:
            update_shipment_status(
                id=99999,
                status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT),
                db=db_conn,
                _api_key=DUMMY_KEY,
            )

        assert exc_info.value.status_code == 404
        assert "no encontrado" in exc_info.value.detail.lower()

    def test_update_status_invalid_enum_raises_validation_error(self):
        """Un estado no contemplado en StatusEnum lanza ValidationError."""
        with pytest.raises(ValidationError):
            StatusUpdateRequest(new_status="EN_CAMINO")

    def test_update_status_modifies_updated_at(self, db_conn):
        """Actualizar el estado actualiza updated_at."""
        shipment = create_shipment(
            shipment_in=ShipmentCreate(order_id=1009, zone=ZoneEnum.LOCAL, recipient_name="Destinatario 1009"),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        shipment_id = shipment["id"]
        result = update_shipment_status(
            id=shipment_id,
            status_in=StatusUpdateRequest(new_status=StatusEnum.IN_TRANSIT),
            db=db_conn,
            _api_key=DUMMY_KEY,
        )
        assert result["updated_at"] >= result["created_at"]
