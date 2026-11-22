# Plan de Tareas — Servicio de Envíos (`servicio-envios`)

**Spec de referencia:** `specs/003-servicio-envios/spec.md` (aprobada)
**Puerto:** 8003 | **BD:** `servicio-envios/envios.db`
**Tests:** `servicio-envios/tests/test_base_auth.py`, `servicio-envios/tests/test_shipments.py`

> **Regla SDD:** Una tarea a la vez. Pruebas primero, luego implementación, luego pausa para revisión.
> Los bloques definen puntos de parada obligatorios (`🛑`).

---

## Bloque 1 — Estructura base, BD, configuración y autenticación

### ✅ T-01 — Estructura de carpetas y archivos base
**RF cubiertos:** RNF-4, RNF-5
**Estado:** ✅ Completada

Crear la siguiente estructura dentro de `servicio-envios/` (sin código funcional aún):

```
servicio-envios/
├── main.py          # Punto de entrada FastAPI
├── config.py        # Carga de variables de entorno con find_dotenv()
├── database.py      # Conexión SQLite nativa y init_db()
├── models.py        # DDL SQL de la tabla shipments
├── schemas.py       # Modelos Pydantic v2 (request/response)
├── auth.py          # verify_api_key() dependency
├── pytest.ini       # rootdir y marcas pytest
└── tests/
    ├── __init__.py
    ├── conftest.py          # Fixtures: app, db en memoria, cliente de prueba
    ├── test_base_auth.py    # Tests de salud, autenticación, zonas y cotización
    └── test_shipments.py    # Tests de CRUD de envíos y máquina de estados
```

**Criterio de finalización:** Todos los archivos creados; `python -c "from config import settings"` no arroja error.

---

### ✅ T-02 — Esquema SQLite de `shipments` y configuración
**RF cubiertos:** RF-1, RNF-5, RNF-7
**Estado:** ✅ Completada

- `config.py`: clase `Settings` con `find_dotenv()` que cargue `API_KEY`, `PORT_ENVIOS`, `RATE_LOCAL`, `RATE_REGIONAL`, `RATE_NACIONAL` y `DB_PATH = servicio-envios/envios.db`.
- `models.py`: constante `CREATE_SHIPMENTS_TABLE_SQL` con el DDL completo de la tabla `shipments` (8 columnas con todos los `CHECK` constraints).
- `database.py`: funciones `get_connection()`, `init_db()`, `get_db()` usando `sqlite3.Row` como `row_factory`.

**Pruebas en `test_base_auth.py`:**
- La BD se crea en memoria para tests (`database_url = ":memory:"`).
- `init_db()` crea la tabla `shipments` sin errores.
- Llamar a `init_db()` dos veces (idempotente) no arroja errores.

---

### ✅ T-03 — Autenticación `X-API-Key`
**RF cubiertos:** RF-9
**Estado:** ✅ Completada

- `auth.py`: función `verify_api_key(x_api_key: str | None = Header(default=None))` que compara con `settings.API_KEY`; retorna HTTP 401 con `WWW-Authenticate: X-API-Key` y mensaje en español si es inválida o está ausente.

**Pruebas en `test_base_auth.py`:**
- Llamar a `verify_api_key()` con la clave correcta → no lanza excepción.
- Llamar con clave incorrecta → lanza `HTTPException` con `status_code=401`.
- Llamar sin clave (header ausente / `None`) → lanza `HTTPException` con `status_code=401`.

---

### ✅ T-04 — Endpoint `GET /health` y arranque
**RF cubiertos:** RF-2, RF-10
**Estado:** ✅ Completada

- `main.py`: app FastAPI con título, descripción y versión. Llama a `init_db()` en el evento `startup`. Endpoint `GET /health` público que retorna `{"status": "ok", "service": "servicio-envios", "version": "0.1.0"}`.

**Pruebas en `test_base_auth.py`:**
- `GET /health` sin `X-API-Key` → HTTP 200, `status == "ok"`.
- `GET /health` con `X-API-Key` incorrecta → HTTP 200 (es público).
- El JSON de respuesta contiene `service` y `version`.

**🛑 PAUSA al terminar T-01 a T-04 — Verificar con `pytest tests/test_base_auth.py` y esperar aprobación para Bloque 2.**

---

## Bloque 2 — Zonas, cotización y CRUD de envíos (creación y consulta)

### ✅ T-05 — Esquemas Pydantic
**RF cubiertos:** RNF-1
**Estado:** ✅ Completada

Definir en `schemas.py` todos los modelos de entrada y salida:

| Modelo | Uso |
|---|---|
| `ZoneEnum` | Enum con valores `LOCAL`, `REGIONAL`, `NACIONAL` |
| `StatusEnum` | Enum con valores `PENDING`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED` |
| `ZoneInfo` | Respuesta de `GET /zones`: `zone`, `rate` |
| `QuoteRequest` | Entrada de `POST /quote`: `zone: ZoneEnum` |
| `QuoteResponse` | Salida de `POST /quote`: `zone`, `shipping_cost` |
| `ShipmentCreate` | Entrada de `POST /shipments`: `order_id`, `zone`, `recipient_name` |
| `ShipmentResponse` | Salida completa de un envío (8 campos) |
| `ShipmentListResponse` | Salida de `GET /shipments`: `items`, `total`, `page`, `page_size` |
| `StatusUpdateRequest` | Entrada de `PATCH /shipments/{id}/status`: `new_status: StatusEnum` |

Validaciones:
- `recipient_name`: `min_length=1`, strip de espacios.
- `page`: `ge=1`.
- `page_size`: `ge=1, le=100`.

---

### ✅ T-06 — `GET /zones` — Consulta de zonas disponibles
**RF cubiertos:** RF-3
**Estado:** ✅ Completada

Endpoint protegido que retorna la lista de 3 zonas con sus tarifas leídas de `settings`.

**Pruebas en `test_base_auth.py`:**
- `GET /zones` sin `X-API-Key` → HTTP 401.
- `GET /zones` con clave correcta → HTTP 200, lista de 3 elementos con `zone` y `rate`.
- Los valores de `rate` coinciden con `RATE_LOCAL`, `RATE_REGIONAL`, `RATE_NACIONAL` del `.env`.

---

### ✅ T-07 — `POST /quote` — Cotización de envío
**RF cubiertos:** RF-4
**Estado:** ✅ Completada

Endpoint protegido que recibe `zone` y retorna `shipping_cost`.

**Pruebas en `test_base_auth.py`:**
- `POST /quote` sin `X-API-Key` → HTTP 401.
- `POST /quote` con zona `LOCAL` → HTTP 200, `shipping_cost == RATE_LOCAL`.
- `POST /quote` con zona `REGIONAL` → HTTP 200, `shipping_cost == RATE_REGIONAL`.
- `POST /quote` con zona `NACIONAL` → HTTP 200, `shipping_cost == RATE_NACIONAL`.
- `POST /quote` con zona inválida (`"local"`, `"EXPRES"`) → HTTP 422.

---

### ✅ T-08 — `POST /shipments` — Creación de envío
**RF cubiertos:** RF-5
**Estado:** ✅ Completada

Endpoint protegido. Crea el registro con `status = PENDING` y `shipping_cost` tomado de `settings` según la zona.

**Pruebas en `test_shipments.py`:**
- `POST /shipments` sin `X-API-Key` → HTTP 401.
- Crear envío con datos válidos → HTTP 201, respuesta con `id`, `status = "PENDING"` y `shipping_cost` correcto.
- `POST /shipments` con `order_id` duplicado → HTTP 409.
- `POST /shipments` con zona inválida → HTTP 422.
- `POST /shipments` con `recipient_name` vacío o solo espacios → HTTP 422.

---

### ✅ T-09 — `GET /shipments/{id}` — Consulta por ID
**RF cubiertos:** RF-6
**Estado:** ✅ Completada

**Pruebas en `test_shipments.py`:**
- Crear un envío y consultarlo por `id` → HTTP 200 con todos los 8 campos.
- Consultar `id` inexistente → HTTP 404 con mensaje en español.
- Consultar con `id` no numérico (`/shipments/abc`) → HTTP 422.

---

### ✅ T-10 — `GET /shipments` — Listado paginado
**RF cubiertos:** RF-7
**Estado:** ✅ Completada

Endpoint protegido. Retorna lista paginada de envíos con filtros opcionales por `status` y `order_id`.

**Pruebas en `test_shipments.py`:**
- Sin registros → HTTP 200, `items = []`, `total = 0`.
- Con 3 envíos creados → HTTP 200, `total = 3`.
- Filtro `?status=PENDING` → retorna solo envíos en ese estado.
- Filtro `?order_id=101` → retorna solo el envío asociado a ese `order_id`.
- Filtro `?status=ENVIADO` (inválido) → HTTP 422.
- `?page_size=0` → HTTP 422; `?page_size=200` → HTTP 422.
- Paginación: 5 envíos, `page=2&page_size=3` → 2 items en la segunda página.

**🛑 PAUSA al terminar T-05 a T-10 — Verificar con `pytest` y esperar aprobación para Bloque 3.**

---

## Bloque 3 — Máquina de estados y criterios de finalización

### ✅ T-11 — `PATCH /shipments/{id}/status` — Actualización de estado
**RF cubiertos:** RF-8
**Estado:** ✅ Completada

Implementar la máquina de estados con las 4 transiciones válidas y rechazo de las demás.

**Pruebas en `test_shipments.py`:**
- Sin `X-API-Key` → HTTP 401.
- `PENDING → IN_TRANSIT` → HTTP 200, `status = "IN_TRANSIT"`.
- `PENDING → CANCELLED` → HTTP 200, `status = "CANCELLED"`.
- `IN_TRANSIT → DELIVERED` → HTTP 200, `status = "DELIVERED"`.
- `IN_TRANSIT → CANCELLED` → HTTP 200, `status = "CANCELLED"`.
- `PENDING → DELIVERED` (inválida) → HTTP 409.
- `DELIVERED → IN_TRANSIT` (desde terminal) → HTTP 409.
- `CANCELLED → PENDING` (desde terminal) → HTTP 409.
- `PENDING → PENDING` (misma transición) → HTTP 409.
- `id` inexistente → HTTP 404.
- `new_status` con valor inválido → HTTP 422.

---

### ✅ T-12 — Casos límite y validaciones adicionales
**RF cubiertos:** Sección 7 de la spec
**Estado:** ✅ Completada

**Pruebas distribuidas en ambos archivos de test:**
- `GET /health` retorna `service` y `version` correctos.
- `GET /zones` retorna exactamente 3 zonas.
- `POST /quote` con `zone` en minúsculas → HTTP 422 (enum estricto).
- `GET /shipments?status=PENDING` con 0 envíos en ese estado → HTTP 200, lista vacía.
- Verificar que `updated_at` cambia después de `PATCH /shipments/{id}/status`.
- `recipient_name` con solo espacios (`"   "`) → HTTP 422.

---

### ✅ T-13 — Verificación de Criterios de Finalización (CF-1 a CF-12)
**RF cubiertos:** Sección 9 de la spec
**Estado:** ✅ Completada

Recorrer la lista de CFs en `spec.md` y marcar cada uno como `[x]`:

- [x] CF-1: Todos los tests pasan (`pytest -q` sin fallos).
- [x] CF-2: `GET /health` → 200 sin `X-API-Key`.
- [x] CF-3: Todos los endpoints protegidos → 401 sin clave válida.
- [x] CF-4: `POST /quote` zona inválida → 422 con mensaje en español.
- [x] CF-5: `POST /shipments` `order_id` duplicado → 409.
- [x] CF-6: `PATCH` transición inválida → 409 con estado actual y transiciones válidas.
- [x] CF-7: `PATCH` transición válida → 200 con recurso actualizado completo.
- [x] CF-8: Envío en estado terminal → 409 ante cualquier cambio de estado.
- [x] CF-9: `GET /zones` → 200 con 3 zonas y tarifas de `.env`.
- [x] CF-10: `/docs` accesible y refleja todos los endpoints.
- [x] CF-11: Sin hardcoding; todo de `.env`.
- [x] CF-12: Mensajes de error en español, identificadores en inglés.

**🛑 PAUSA FINAL — Ejecutar `pytest servicio-envios/tests -q` para verificar que todos los tests pasen y esperar aprobación antes de hacer commit de Fase 3.**

---

## Resumen del plan

| Bloque | Tareas | Tests | Pausa |
|---|---|---|---|
| **Bloque 1** | T-01 a T-04 | `test_base_auth.py` (parcial) | 🛑 Después de T-04 |
| **Bloque 2** | T-05 a T-10 | `test_base_auth.py` + `test_shipments.py` (parcial) | 🛑 Después de T-10 |
| **Bloque 3** | T-11 a T-13 | `test_shipments.py` completo | 🛑 Después de T-13 |

**Total estimado de tests:** ~55–65 pruebas en 2 archivos.
