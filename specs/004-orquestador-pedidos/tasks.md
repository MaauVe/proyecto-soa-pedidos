# Plan de Tareas — Servicio Orquestador de Pedidos (`servicio-pedidos`)

**Spec de referencia:** `specs/004-orquestador-pedidos/spec.md` (aprobada ✅)  
**Puerto:** 8004 | **BD:** `servicio-pedidos/pedidos.db`  
**Tests:** `servicio-pedidos/tests/test_auth.py`, `servicio-pedidos/tests/test_clients.py`, `servicio-pedidos/tests/test_create_order.py`, `servicio-pedidos/tests/test_get_order.py`, `servicio-pedidos/tests/test_list_orders.py`, `servicio-pedidos/tests/test_cancel_order.py`

> **Regla SDD:** Una tarea a la vez. Pruebas primero, luego implementación, luego pausa para revisión.  
> Los bloques definen puntos de parada obligatorios (`🛑`).

---

## Estado de las Tareas

| ID   | Tarea                                                             | RF / CF cubiertos               | Estado       |
|------|-------------------------------------------------------------------|---------------------------------|--------------|
| T-14 | Estructura base del proyecto (`servicio-pedidos/`)                | —                               | ✅ Completada |
| T-15 | Modelo de datos y BD (tablas `orders` + `order_items`)            | RF-3.4, RNF-7                   | ✅ Completada |
| T-16 | Config, auth `X-API-Key` y `GET /health`                          | RF-1, RF-2, CF-1, CF-2          | ✅ Completada |
| T-17 | Módulo `clients.py` — cliente HTTP `httpx` para 3 servicios       | RF-7, RNF-3, RNF-4              | ✅ Completada |
| T-18 | `POST /orders` — flujo completo + Saga de compensación            | RF-3 (3.1–3.8), CF-3–7          | ✅ Completada |
| T-19 | `GET /orders/{id}` — detalle con estado de envío degradado        | RF-4, CF-8, CF-9                | ⬜ Pendiente |
| T-20 | `GET /orders` — listado paginado con filtros                      | RF-5, CF-10                     | ⬜ Pendiente |
| T-21 | `PATCH /orders/{id}/cancel` — cancelación con Saga                | RF-6, CF-11–13                  | ⬜ Pendiente |
| T-22 | Revisión final y criterios de finalización (CF-1 a CF-17)         | Todos los CF                    | ⬜ Pendiente |

---

## Bloque 1 — Estructura base, BD, configuración y autenticación

### T-14 — Estructura de carpetas y archivos base
**RF cubiertos:** RNF-3, RNF-5, RNF-6  
**Estado:** ✅ Completada

Crear la siguiente estructura dentro de `servicio-pedidos/` (sin código funcional de negocio aún):

```
servicio-pedidos/
├── main.py          # Punto de entrada FastAPI (lifespan + health check)
├── config.py        # Carga de variables de entorno con find_dotenv()
├── database.py      # Conexión SQLite nativa y init_db()
├── schemas.py       # Modelos Pydantic (inicialmente vacío / esquemas base)
├── auth.py          # verify_api_key() dependency
├── clients.py       # Clientes httpx hacia los 3 servicios externos (stub)
├── pytest.ini       # rootdir y marcas pytest
└── tests/
    ├── __init__.py
    ├── conftest.py          # Fixtures: app TestClient, BD en memoria
    ├── test_auth.py         # Tests de /health y autenticación
    ├── test_clients.py      # Tests del módulo clients.py (mocks httpx)
    ├── test_create_order.py # Tests de POST /orders
    ├── test_get_order.py    # Tests de GET /orders/{id}
    ├── test_list_orders.py  # Tests de GET /orders
    └── test_cancel_order.py # Tests de PATCH /orders/{id}/cancel
```

**Notas:**
- No se crean `requirements.txt` ni `.env` propios; se reutilizan los de la raíz.
- El `.env.example` raíz ya tiene `PORT_PEDIDOS`, `URL_CLIENTES`, `URL_INVENTARIO`, `URL_ENVIOS`, `DB_PEDIDOS`, `API_KEY`. Verificar que `HTTP_TIMEOUT_SECONDS=10` esté presente.
- `config.py` expone: `PORT`, `API_KEY`, `URL_CLIENTES`, `URL_INVENTARIO`, `URL_ENVIOS`, `DB_PEDIDOS`, `HTTP_TIMEOUT_SECONDS` (default 10).

**Criterio de done:** `uvicorn main:app --port 8004` arranca sin errores desde `servicio-pedidos/`; `GET /docs` es accesible.

---

### T-15 — Esquema SQLite de `orders` y `order_items`
**RF cubiertos:** RF-3.4, RNF-7  
**Estado:** ✅ Completada

- `database.py`: funciones `get_db()` (conexión SQLite con `row_factory = sqlite3.Row`) e `init_db()` que ejecuta los `CREATE TABLE IF NOT EXISTS` para `orders` (11 columnas) y `order_items` (7 columnas) según la spec §6.
- `pedidos.db` arranca **vacía** (sin datos semilla).

**Pruebas en `tests/test_auth.py` (sección BD):**
- `init_db()` crea las tablas correctamente en BD de prueba en memoria.
- Columnas de `orders`: `id`, `customer_id`, `customer_name`, `coverage_zone`, `shipping_cost`, `total_amount`, `status`, `shipment_id`, `compensation_error`, `created_at`, `updated_at`.
- Columnas de `order_items`: `id`, `order_id`, `product_id`, `product_name`, `unit_price`, `quantity`, `subtotal`.
- `init_db()` es idempotente (ejecutar dos veces no arroja error).

**Criterio de done:** pruebas de BD pasan en verde.

---

### T-16 — Config, auth `X-API-Key` y `GET /health`
**RF cubiertos:** RF-1, RF-2, CF-1, CF-2  
**Estado:** ✅ Completada

- `auth.py`: `verify_api_key()` dependencia FastAPI que compara el header `X-API-Key` con `config.API_KEY`; retorna 401 con mensaje en español si ausente o inválida.
- `GET /health` público → `{ "service": "servicio-pedidos", "status": "ok", "version": "0.1.0", "port": 8004 }`.

**Pruebas en `tests/test_auth.py`:**
- `GET /health` sin `X-API-Key` → HTTP 200, `status == "ok"`.
- `GET /health` con `X-API-Key` incorrecta → HTTP 200 (es público).
- Endpoint protegido sin `X-API-Key` → HTTP 401.
- Endpoint protegido con clave incorrecta → HTTP 401.
- Endpoint protegido con clave correcta → no es 401.

**🛑 PAUSA al terminar T-14 a T-16 — Verificar con `pytest tests/test_auth.py` y esperar aprobación para Bloque 2.**

---

## Bloque 2 — Cliente HTTP y `POST /orders` con Saga

### T-17 — Módulo `clients.py` — cliente HTTP `httpx`
**RF cubiertos:** RF-3.1–3.3, RF-3.5–3.6, RF-7, RNF-3, RNF-4  
**Estado:** ✅ Completada

Encapsular todas las llamadas HTTP salientes en `clients.py`:

| Función | Llama a | Descripción y Mapeo Exacto |
|---|---|---|
| `validate_customer(customer_id)` | `GET /customers/{id}/validate` (8001) | Retorna `dict` con campos `full_name` (mapea a `customer_name`), `coverage_zone` (mapea a `coverage_zone`), `delivery_address`; eleva 422 si 404/409 |
| `reserve_stock(items)` | `POST /products/reserve` (8002) | Retorna lista `reserved` con `name` (mapea a `product_name`), `unit_price`, `quantity_reserved` (mapea a `quantity`), `weight_kg`; eleva 422 si 409 |
| `release_stock(items)` | `POST /products/release` (8002) | Envía `items` (`product_id`, `quantity`); retorna lista `released`; eleva 500/503 si falla |
| `quote_shipment(zone)` | `POST /quote` (8003) | Envía `zone` (`LOCAL`/`REGIONAL`/`NACIONAL`); retorna `shipping_cost: float`; eleva 502 si falla |
| `create_shipment(order_id, zone, recipient_name)` | `POST /shipments` (8003) | Envía `order_id`, `zone`, `recipient_name`; retorna dict con `id` (mapea a `shipment_id`); eleva 502 si falla |
| `get_shipment(shipment_id)` | `GET /shipments/{id}` (8003) | Retorna dict con `status` (mapea a `shipment_status`); retorna `None` si falla (modo degradado) |
| `cancel_shipment(shipment_id)` | `PATCH /shipments/{id}/status` (8003) | Envía `{"new_status": "CANCELLED"}`; eleva 502 si falla |

Todas las funciones capturan `httpx.ConnectError` y `httpx.TimeoutException` → `HTTPException 503`.

**Pruebas en `tests/test_clients.py`** (con `pytest-httpx` o `unittest.mock.patch`):
- Respuesta exitosa de cada función retorna el valor esperado.
- `ConnectError` en cualquier función → `HTTPException 503`.
- `TimeoutException` en cualquier función → `HTTPException 503`.
- Respuesta 404 de `validate_customer` → `HTTPException 422`.
- Respuesta 409 de `validate_customer` → `HTTPException 422`.
- Respuesta 409 de `reserve_stock` → `HTTPException 422`.
- `get_shipment` con servicio caído → retorna `None` (no eleva excepción).

**Criterio de done:** `pytest tests/test_clients.py` pasa en verde.

---

### T-18 — `POST /orders` — flujo completo + Saga
**RF cubiertos:** RF-3 (3.1–3.8), RNF-7, CF-3–7  
**Estado:** ✅ Completada

Endpoint `POST /orders` con body `{ "customer_id": int, "items": [{"product_id": int, "quantity": int}] }`.

Secuencia de orquestación (5 pasos):
1. `validate_customer` → 422 si cliente no válido.
2. `reserve_stock` → 422 si stock insuficiente.
3. `quote_shipment` → si falla: `release_stock` + 502.
4. INSERT `orders` + `order_items` en transacción atómica (`status=PENDING`) → si falla: `release_stock` + 500.
5. `create_shipment` → si falla: `release_stock` + DELETE pedido + 502; si compensación también falla: pedido con `status=FAILED` + `compensation_error` + 500.
- En éxito: UPDATE `status=CONFIRMED` + `shipment_id`; responder 201 con pedido completo.

**Pruebas en `tests/test_create_order.py`** (todos los servicios externos mockeados):
- Flujo exitoso completo → 201, `status="CONFIRMED"`, `shipment_id` poblado, `items` con snapshots correctos.
- `customer_id` inexistente → 422, sin reserva de stock.
- Cliente inactivo → 422, sin reserva de stock.
- Stock insuficiente → 422, sin modificación en pedidos.
- Fallo en `quote_shipment` tras reservar stock → 502 + stock liberado.
- Fallo en INSERT pedido → 500 + stock liberado.
- Fallo en `create_shipment` → 502 + stock liberado + pedido eliminado.
- Fallo en `create_shipment` + fallo en `release_stock` → 500 + pedido con `status=FAILED`.
- `items: []` → 422.
- `product_id` duplicado en `items` → 422.
- `customer_id ≤ 0` → 422.
- `quantity ≤ 0` → 422.
- Sin `X-API-Key` → 401.

**Criterio de done:** `pytest tests/test_create_order.py` pasa en verde.

**🛑 PAUSA al terminar T-17 a T-18 — Verificar con `pytest tests/test_clients.py tests/test_create_order.py` y esperar aprobación para Bloque 3.**

---

## Bloque 3 — Consulta, listado y cancelación

### T-19 — `GET /orders/{id}` — detalle con estado de envío degradado
**RF cubiertos:** RF-4, CF-8, CF-9  
**Estado:** ⬜ Pendiente

Endpoint que retorna el pedido completo con sus `items` y el estado actual del envío obtenido de `servicio-envios`. Si `servicio-envios` falla, responde 200 con `shipment_status: null` y `shipment_detail: "No disponible temporalmente"`.

**Pruebas en `tests/test_get_order.py`:**
- Pedido existente con `servicio-envios` disponible → 200 con `shipment_status` real (ej. `"PENDING"`).
- Pedido existente con `servicio-envios` caído → 200 con `shipment_status: null` y `shipment_detail: "No disponible temporalmente"`.
- Pedido existente con `shipment_id = null` → 200 con `shipment_status: null`.
- Pedido con `status = FAILED` → 200 con datos completos y `compensation_error` poblado.
- `id` inexistente → 404 con mensaje en español.
- Sin `X-API-Key` → 401.

**Criterio de done:** `pytest tests/test_get_order.py` pasa en verde.

---

### T-20 — `GET /orders` — listado paginado con filtros
**RF cubiertos:** RF-5, CF-10  
**Estado:** ⬜ Pendiente

Endpoint que lista pedidos solo desde `pedidos.db` (sin consultar servicios externos). Query params: `page` (≥1, default 1), `page_size` (1–100, default 20), `status` (opcional), `customer_id` (opcional). Responde con resumen de pedido por ítem (sin `order_items` ni bloque completo de envío).

**Pruebas en `tests/test_list_orders.py`:**
- Sin parámetros → 200 con paginación por defecto (`page=1`, `page_size=20`).
- Filtro `status=CONFIRMED` → solo pedidos confirmados.
- Filtro `customer_id=1` → solo pedidos de ese cliente.
- BD vacía → 200, `items: []`, `total: 0`.
- `page` más allá del total → 200 con `items: []`, `total` real.
- `page_size=0` → 422; `page_size=200` → 422.
- Sin `X-API-Key` → 401.

**Criterio de done:** `pytest tests/test_list_orders.py` pasa en verde.

---

### T-21 — `PATCH /orders/{id}/cancel` — cancelación con Saga
**RF cubiertos:** RF-6, CF-11–13  
**Estado:** ⬜ Pendiente

Endpoint que cancela un pedido activo. Verifica el estado del envío antes de proceder: solo cancela si el envío está en `PENDING`; rechaza con 409 si está en `IN_TRANSIT` o `DELIVERED`. Si el envío ya está `CANCELLED`, omite la llamada a `servicio-envios` y libera el stock directamente.

**Pruebas en `tests/test_cancel_order.py`:**
- Pedido con envío `PENDING` → 200: cancela envío, libera stock, actualiza pedido a `CANCELLED`.
- Pedido con envío `IN_TRANSIT` → 409 "No se puede cancelar…", pedido sin modificar.
- Pedido con envío `DELIVERED` → 409 "No se puede cancelar…", pedido sin modificar.
- Pedido con envío ya `CANCELLED` → 200: omite llamada a envíos, libera stock, actualiza pedido.
- Pedido con `status = CANCELLED` → 409 "ya está en estado terminal".
- Pedido con `status = FAILED` → 409 "ya está en estado terminal".
- Fallo al cancelar envío en `servicio-envios` → 502, pedido sin modificar.
- Fallo al liberar stock en `servicio-inventario` → 502, pedido sin modificar.
- `id` inexistente → 404 con mensaje en español.
- Sin `X-API-Key` → 401.

**Criterio de done:** `pytest tests/test_cancel_order.py` pasa en verde.

---

### T-22 — Verificación de Criterios de Finalización (CF-1 a CF-17)
**RF cubiertos:** Sección 10 de la spec  
**Estado:** ⬜ Pendiente

Recorrer la lista de CFs en `spec.md` y marcar cada uno:

- [ ] CF-1:  `GET /health` responde 200 sin `X-API-Key`.
- [ ] CF-2:  Cualquier endpoint protegido sin `X-API-Key` válida responde 401.
- [ ] CF-3:  `POST /orders` completa el flujo de 5 pasos y responde 201 con el pedido completo.
- [ ] CF-4:  `POST /orders` con cliente inactivo/inexistente responde 422 sin reservar stock.
- [ ] CF-5:  `POST /orders` con stock insuficiente responde 422 sin modificar pedidos.
- [ ] CF-6:  `POST /orders` dispara compensación automática si falla `servicio-envios` tras reservar stock y responde 502.
- [ ] CF-7:  Si la compensación también falla, el pedido queda con `status=FAILED` y `compensation_error` poblado.
- [ ] CF-8:  `GET /orders/{id}` devuelve 404 para pedido inexistente.
- [ ] CF-9:  `GET /orders/{id}` devuelve 200 con `shipment_status: null` cuando `servicio-envios` no responde.
- [ ] CF-10: `GET /orders` lista pedidos con paginación y filtros `status` / `customer_id`.
- [ ] CF-11: `PATCH /orders/{id}/cancel` cancela exitosamente un pedido con envío en `PENDING`.
- [ ] CF-12: `PATCH /orders/{id}/cancel` rechaza con 409 si el envío está `IN_TRANSIT` o `DELIVERED`.
- [ ] CF-13: `PATCH /orders/{id}/cancel` con envío ya `CANCELLED` libera el stock y actualiza el pedido localmente.
- [ ] CF-14: Todos los errores de red (`ConnectError`, `TimeoutException`) se capturan y retornan 502 o 503.
- [ ] CF-15: Ninguna URL, clave ni secreto está hardcodeado en el código fuente.
- [ ] CF-16: La suite `pytest` cubre CF-1 a CF-15 con mocks de servicios externos.
- [ ] CF-17: `GET /docs` y `GET /redoc` son accesibles con la aplicación corriendo.

**🛑 PAUSA FINAL — Ejecutar `pytest servicio-pedidos/tests -q` para verificar que todos los tests pasen y esperar aprobación antes de hacer commit de Fase 4.**

---

## Resumen del plan

| Bloque | Tareas | Archivos de test principales | Pausa |
|---|---|---|---|
| **Bloque 1** | T-14 a T-16 | `test_auth.py` | 🛑 Después de T-16 |
| **Bloque 2** | T-17 a T-18 | `test_clients.py`, `test_create_order.py` | 🛑 Después de T-18 |
| **Bloque 3** | T-19 a T-22 | `test_get_order.py`, `test_list_orders.py`, `test_cancel_order.py` | 🛑 Después de T-22 |

**Total estimado de tests:** ≥ 50 pruebas en 6 archivos.
