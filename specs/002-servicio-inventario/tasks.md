# Tasks — Servicio de Catálogo e Inventario (`servicio-inventario`)

**Spec:** `specs/002-servicio-inventario/spec.md` (aprobada)
**Puerto:** 8002 | **BD:** `inventario.db` | **Carpeta:** `servicio-inventario/`
**Regla SDD:** Una tarea a la vez. Escribir pruebas `pytest` primero, implementar hasta que pasen, detenerse y reportar.

---

## Estado global

| Tarea | Descripción corta | Estado |
|---|---|---|
| T-01 | Estructura base y configuración | ✅ Completada |
| T-02 | Esquema de BD y modelo SQLite | ✅ Completada |
| T-03 | Seed de datos iniciales | ✅ Completada |
| T-04 | Autenticación `X-API-Key` y `/health` | ✅ Completada |
| T-05 | `POST /products` — Crear producto | ⬜ Pendiente |
| T-06 | `GET /products/{id}` — Consulta por ID | ⬜ Pendiente |
| T-07 | `GET /products` — Listado paginado | ⬜ Pendiente |
| T-08 | `PATCH /products/{id}` — Actualización parcial | ⬜ Pendiente |
| T-09 | `DELETE /products/{id}` — Desactivación lógica | ⬜ Pendiente |
| T-10 | `PATCH /products/{id}/reactivate` — Reactivación | ⬜ Pendiente |
| T-11 | `POST /products/reserve` — Reserva atómica | ⬜ Pendiente |
| T-12 | `POST /products/release` — Liberación de stock | ⬜ Pendiente |
| T-13 | `POST /products/check-availability` — Consulta sin descuento | ⬜ Pendiente |
| T-14 | Integración final y criterios de finalización CF-1…CF-12 | ⬜ Pendiente |

---

## T-01 — Estructura base y configuración ✅

**RF cubiertos:** RNF-2, RNF-6, RNF-8  
**Objetivo:** Crear el andamiaje mínimo del servicio: carpeta, archivos de configuración y arranque básico del servidor sin ningún endpoint de negocio. Se utiliza el `requirements.txt` y `.env` de la raíz del proyecto mediante `find_dotenv()`, almacenando `inventario.db` dentro de `servicio-inventario/`.

**Archivos a crear:**
```
servicio-inventario/
├── main.py          ← instancia FastAPI, incluye routers, arranca con uvicorn
├── config.py        ← carga variables de entorno con python-dotenv (find_dotenv)
├── database.py      ← conexión y creación de tablas SQLite nativas (inventario.db)
├── models.py        ← definición de tabla `products` (SQL DDL en Python)
├── schemas.py       ← modelos Pydantic de entrada/salida
├── seed.py          ← carga de datos semilla (5 productos, 1 inactivo con stock 0)
├── auth.py          ← dependencia FastAPI para validar X-API-Key
├── pytest.ini       ← configuración de pytest
└── tests/
    ├── __init__.py
    ├── conftest.py  ← fixtures: BD en memoria/aislada, setup de pruebas
    ├── test_base_auth.py     ← pruebas de T-01, T-02, T-03 y T-04
    ├── test_products_crud.py  ← pruebas de T-05 a T-10 (CRUD completo)
    └── test_stock_ops.py      ← pruebas de T-11 a T-13 (reserva, release, disponibilidad)
```

**Pruebas consolidadas en `tests/test_base_auth.py`:**
- [x] El módulo `config.py` carga `API_KEY`, `PORT_INVENTARIO` y `DB_INVENTARIO` desde el `.env` raíz vía `find_dotenv()`.
- [x] El módulo `database.py` crea la tabla `products` al llamar `init_db()` sin errores.
- [x] `GET /health` responde HTTP 200 con `{"service": "servicio-inventario", "status": "ok", "version": "0.1.0", "port": 8002}` sin requerir `X-API-Key`.

**Criterio de completado:** Tests pasan; `uvicorn main:app --port 8002` arranca sin errores.

---

## T-02 — Esquema de BD y modelo SQLite ✅

**RF cubiertos:** RF-1 (parcial: solo esquema), RNF-6  
**Objetivo:** Definir la tabla `products` con todos sus campos y restricciones en SQLite.

**Campos de la tabla `products`:**

| Campo | Tipo SQLite | Restricción |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| `sku` | TEXT | NOT NULL, UNIQUE (guardado en mayúsculas) |
| `name` | TEXT | NOT NULL |
| `description` | TEXT | nullable |
| `unit_price` | REAL | NOT NULL, CHECK > 0 |
| `weight_kg` | REAL | NOT NULL, CHECK > 0 |
| `stock` | INTEGER | NOT NULL, DEFAULT 0, CHECK >= 0 |
| `is_active` | INTEGER | NOT NULL, DEFAULT 1 (booleano) |
| `created_at` | TEXT | NOT NULL (ISO 8601 UTC) |
| `updated_at` | TEXT | NOT NULL (ISO 8601 UTC) |

**Pruebas en `tests/test_base_auth.py`:**
- [x] `init_db()` crea la tabla `products` con todos los campos esperados (verificar con `PRAGMA table_info`).
- [x] No falla si se llama `init_db()` dos veces (idempotente, usa `CREATE TABLE IF NOT EXISTS`).
- [x] Un INSERT directo con `stock = -1` lanza `IntegrityError` (CHECK constraint).
- [x] Un INSERT directo con `unit_price = 0` lanza `IntegrityError` (CHECK constraint).
- [x] Un INSERT directo con `weight_kg = 0` lanza `IntegrityError` (CHECK constraint).
- [x] Un INSERT con SKU duplicado lanza `IntegrityError` (UNIQUE constraint).

**Criterio de completado:** Tests pasan.

---

## T-03 — Seed de datos iniciales ✅

**RF cubiertos:** RF-1 (completo)  
**Objetivo:** Implementar la carga automática de 5 productos de prueba si la tabla está vacía al arrancar (incluyendo 1 inactivo con stock 0).

**Productos semilla:**
1. SKU: `LAPTOP-001`, nombre: `Laptop Ultradelgada 14"`, precio: 12500.00, peso: 1.5 kg, stock: 20
2. SKU: `MOUSE-002`, nombre: `Mouse Inalámbrico Ergonómico`, precio: 350.00, peso: 0.15 kg, stock: 150
3. SKU: `TECLADO-003`, nombre: `Teclado Mecánico RGB`, precio: 980.00, peso: 0.9 kg, stock: 75
4. SKU: `MONITOR-004`, nombre: `Monitor 27" 4K UHD`, precio: 8900.00, peso: 5.2 kg, stock: 10
5. SKU: `AURICULARES-005`, nombre: `Auriculares Bluetooth ANC`, precio: 1450.00, peso: 0.3 kg, stock: 0, `is_active: false`

**Pruebas en `tests/test_base_auth.py`:**
- [x] `seed_products()` inserta exactamente 5 productos en tabla vacía.
- [x] `seed_products()` sobre tabla con datos existentes **no** inserta ni modifica nada.
- [x] Los productos semilla tienen los campos `sku`, `name`, `unit_price`, `weight_kg`, `stock` e `is_active` correctamente poblados.
- [x] Al menos un producto semilla tiene `is_active = false` y `stock = 0`.

**Criterio de completado:** Tests pasan.

---

## T-04 — Autenticación `X-API-Key` y endpoint `/health` ✅

**RF cubiertos:** RF-11, RF-12  
**Objetivo:** Implementar la dependencia de autenticación reutilizable y el único endpoint público.

**Pruebas en `tests/test_base_auth.py`:**
- [x] `GET /health` → HTTP 200, sin `X-API-Key` en el header.
- [x] `GET /health` → el body contiene `service`, `status: "ok"`, `version` y `port`.
- [x] Cualquier llamada sin `X-API-Key` o vacía a verify_api_key → HTTP 401.
- [x] Cualquier llamada con `X-API-Key` incorrecta → HTTP 401.
- [x] Llamada con `X-API-Key` correcta → retorna la clave sin lanzar excepción.

**Criterio de completado:** Tests pasan.

---

## T-05 — `POST /products` — Crear producto

**RF cubiertos:** RF-2  
**Objetivo:** Crear productos con validaciones completas de campos y unicidad de SKU.

**Contrato del endpoint:**
- **Request body:** `sku`, `name`, `description?`, `unit_price`, `weight_kg`, `stock`
- **Response 201:** producto completo con `id`, todos los campos y `is_active: true`
- **Response 409:** SKU duplicado (insensible a mayúsculas)
- **Response 422:** campo requerido ausente, `unit_price ≤ 0`, `weight_kg ≤ 0`, `stock < 0`

**Pruebas a escribir primero (`tests/test_create_product.py`):**
- [ ] Crear producto válido → HTTP 201 con todos los campos poblados.
- [ ] `is_active` es `true` por defecto al crear.
- [ ] `created_at` y `updated_at` están presentes y son strings ISO 8601.
- [ ] SKU duplicado (mismo case) → HTTP 409.
- [ ] SKU duplicado (distinto case, ej. `PROD-01` vs `prod-01`) → HTTP 409.
- [ ] `unit_price = 0` → HTTP 422.
- [ ] `unit_price` negativo → HTTP 422.
- [ ] `weight_kg = 0` → HTTP 422.
- [ ] `weight_kg` negativo → HTTP 422.
- [ ] `stock` negativo → HTTP 422.
- [ ] `stock = 0` → HTTP 201 (es válido).
- [ ] Campo requerido `name` ausente → HTTP 422.
- [ ] Campo `description` ausente → HTTP 201 (es opcional).
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 14 tests pasan.

---

## T-06 — `GET /products/{id}` — Consulta por ID

**RF cubiertos:** RF-3  
**Objetivo:** Retornar un producto por su ID con todos los campos, o 404 si no existe.

**Pruebas a escribir primero (`tests/test_get_product.py`):**
- [ ] ID existente → HTTP 200 con todos los campos del producto.
- [ ] ID no existente → HTTP 404 con mensaje en español.
- [ ] ID no numérico (ej. `/products/abc`) → HTTP 422.
- [ ] Producto inactivo → HTTP 200 (se retorna igual, `is_active: false`).
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 5 tests pasan.

---

## T-07 — `GET /products` — Listado paginado

**RF cubiertos:** RF-4  
**Objetivo:** Listar productos con paginación y filtro opcional por `is_active`.

**Contrato del endpoint:**
- **Query params:** `page` (default 1), `page_size` (default 20, rango 1–100), `is_active` (opcional)
- **Response 200:** `{ items: [...], total, page, page_size, total_pages }`

**Pruebas a escribir primero (`tests/test_list_products.py`):**
- [ ] Sin parámetros → HTTP 200, paginación por defecto aplicada.
- [ ] `is_active=true` → solo productos activos.
- [ ] `is_active=false` → solo productos inactivos.
- [ ] Sin filtro → todos los productos (activos e inactivos).
- [ ] `page_size=0` → HTTP 422.
- [ ] `page_size=200` → HTTP 422.
- [ ] BD vacía → HTTP 200 con `items: []` y `total: 0`.
- [ ] Metadatos de paginación (`total`, `page`, `page_size`, `total_pages`) presentes en la respuesta.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 9 tests pasan.

---

## T-08 — `PATCH /products/{id}` — Actualización parcial

**RF cubiertos:** RF-5  
**Objetivo:** Actualizar uno o más campos de un producto sin afectar los no proporcionados.

**Pruebas a escribir primero (`tests/test_update_product.py`):**
- [ ] Actualizar solo `name` → HTTP 200, solo ese campo cambia.
- [ ] Actualizar solo `unit_price` → HTTP 200.
- [ ] Cuerpo vacío `{}` → HTTP 200, producto sin cambios (no-op).
- [ ] `updated_at` se actualiza tras un PATCH exitoso.
- [ ] ID no existente → HTTP 404.
- [ ] Cambiar `sku` a uno ya usado por otro producto → HTTP 409.
- [ ] Cambiar `sku` al mismo valor del producto (mismo ID) → HTTP 200 (no es duplicado).
- [ ] `unit_price = 0` en PATCH → HTTP 422.
- [ ] `weight_kg` negativo en PATCH → HTTP 422.
- [ ] `stock` negativo en PATCH → HTTP 422.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 11 tests pasan.

---

## T-09 — `DELETE /products/{id}` — Desactivación lógica

**RF cubiertos:** RF-6  
**Objetivo:** Marcar `is_active = false` sin borrar el registro ni modificar el stock.

**Pruebas a escribir primero (`tests/test_deactivate_product.py`):**
- [ ] Producto activo → HTTP 200 con `is_active: false`.
- [ ] Stock no cambia después de desactivar (verificar con `GET /products/{id}`).
- [ ] Registro sigue siendo consultable por `GET /products/{id}`.
- [ ] Producto ya inactivo → HTTP 409 con mensaje en español.
- [ ] ID no existente → HTTP 404.
- [ ] Producto con `stock > 0` → se desactiva igualmente (HTTP 200).
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 7 tests pasan.

---

## T-10 — `PATCH /products/{id}/reactivate` — Reactivación

**RF cubiertos:** RF-7  
**Objetivo:** Restaurar `is_active = true` en un producto previamente desactivado.

**Pruebas a escribir primero (`tests/test_reactivate_product.py`):**
- [ ] Producto inactivo → HTTP 200 con `is_active: true`.
- [ ] Producto ya activo → HTTP 409 con mensaje en español.
- [ ] ID no existente → HTTP 404.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Los 4 tests pasan.

---

## T-11 — `POST /products/reserve` — Reserva atómica de stock

**RF cubiertos:** RF-8  
**Objetivo:** Descontar stock de múltiples productos de forma atómica; rollback total ante cualquier falla. Incluye metadatos del producto en la respuesta exitosa y rechaza listas con `product_id` duplicados.

**Contrato del endpoint:**
- **Request body:** `{ items: [{ product_id, quantity }] }`
- **Response 200:** `{ reserved: [{ product_id, name, unit_price, weight_kg, quantity_reserved, stock_remaining }] }`
- **Response 409:** al menos un ítem falla — lista de errores por producto, **ningún** stock se modifica
- **Response 422:** lista vacía, `quantity ≤ 0`, o `product_id` duplicados en la lista `items`

**Pruebas a escribir en `tests/test_stock_ops.py`:**
- [ ] Reserva de un solo producto con stock suficiente → HTTP 200, stock decrementado, incluye `name`, `unit_price`, `weight_kg`.
- [ ] Reserva de múltiples productos, todos con stock → HTTP 200, todos decrementados.
- [ ] Un producto sin stock suficiente → HTTP 409, **todos** los demás productos sin cambio de stock.
- [ ] Un producto inactivo en la lista → HTTP 409, rollback total.
- [ ] `product_id` inexistente en la lista → HTTP 409, rollback total.
- [ ] Lista de ítems con `product_id` duplicados → HTTP 422.
- [ ] Lista de ítems vacía `[]` → HTTP 422.
- [ ] `quantity = 0` en un ítem → HTTP 422.
- [ ] `quantity` negativa en un ítem → HTTP 422.
- [ ] Reservar exactamente el stock disponible (stock = quantity) → HTTP 200, stock resultante = 0.
- [ ] Reservar más del stock disponible (ej. stock=5, quantity=6) → HTTP 409 con mensaje indicando disponible vs. solicitado.
- [ ] La respuesta de error 409 incluye qué producto falló y el motivo.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Tests pasan.

---

## T-12 — `POST /products/release` — Liberación de stock

**RF cubiertos:** RF-9  
**Objetivo:** Sumar stock a productos (incluidos inactivos) al cancelar un pedido.

**Contrato del endpoint:**
- **Request body:** `{ items: [{ product_id, quantity }] }`
- **Response 200:** `{ released: [{ product_id, quantity_released, stock_after }] }`
- **Response 404:** algún `product_id` no existe — no se modifica ningún otro
- **Response 422:** lista vacía, `quantity ≤ 0`

**Pruebas a escribir en `tests/test_stock_ops.py`:**
- [ ] Liberar stock de un producto activo → HTTP 200, stock incrementado correctamente.
- [ ] Liberar stock de un producto **inactivo** → HTTP 200, stock incrementado igual.
- [ ] Liberar stock de múltiples productos → HTTP 200, todos incrementados.
- [ ] `product_id` inexistente → HTTP 404, ningún otro producto modificado.
- [ ] Lista vacía `[]` → HTTP 422.
- [ ] `quantity = 0` → HTTP 422.
- [ ] `quantity` negativa → HTTP 422.
- [ ] `updated_at` del producto se actualiza tras liberar stock.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Tests pasan.

---

## T-13 — `POST /products/check-availability` — Consulta sin descuento

**RF cubiertos:** RF-10  
**Objetivo:** Verificar disponibilidad de múltiples productos sin modificar el stock. Incluye `name`, `unit_price`, `weight_kg` por ítem y valida duplicados en `items` con HTTP 422.

**Contrato del endpoint:**
- **Request body:** `{ items: [{ product_id, quantity }] }`
- **Response 200 (siempre, incluso con indisponibilidades):**
  ```json
  {
    "all_available": false,
    "results": [
      { "product_id": 1, "name": "...", "unit_price": 100.0, "weight_kg": 1.5, "available": true,  "stock_current": 20, "quantity_requested": 5 },
      { "product_id": 2, "name": "...", "unit_price": 50.0, "weight_kg": 0.5, "available": false, "reason": "Stock insuficiente: solicitado 10, disponible 3" }
    ]
  }
  ```
- **Response 422:** lista vacía, `quantity ≤ 0`, o `product_id` duplicados en `items`

**Pruebas a escribir en `tests/test_stock_ops.py`:**
- [ ] Todos los productos disponibles → HTTP 200 con `all_available: true`, incluye `name`, `unit_price`, `weight_kg`.
- [ ] Al menos uno no disponible → HTTP 200 con `all_available: false` (no es error, es información).
- [ ] Lista con `product_id` duplicados → HTTP 422.
- [ ] Stock no se modifica después de la consulta (verificar con `GET /products/{id}`).
- [ ] Producto inactivo → `available: false` con razón `"El producto se encuentra inactivo"`.
- [ ] `product_id` inexistente → `available: false` con razón `"Producto no encontrado"`.
- [ ] Lista vacía → HTTP 422.
- [ ] Sin `X-API-Key` → HTTP 401.

**Criterio de completado:** Tests pasan.

---

## T-14 — Integración final y criterios de finalización

**RF cubiertos:** CF-1 … CF-12  
**Objetivo:** Verificar que todos los criterios de la spec están cumplidos como sistema integrado.

**Checklist de verificación:**
- [ ] **CF-1:** Suite completa de tests pasa (`pytest tests/ -v` sin fallos).
- [ ] **CF-2:** `GET /health` → HTTP 200 sin `X-API-Key`.
- [ ] **CF-3:** Todos los endpoints protegidos → HTTP 401 sin key o con key incorrecta.
- [ ] **CF-4:** `POST /products` con SKU duplicado (cualquier case) → HTTP 409.
- [ ] **CF-5:** `POST /products/reserve` con ítem sin stock → HTTP 409 y todos los demás stocks intactos.
- [ ] **CF-6:** `POST /products/release` sobre producto inactivo → HTTP 200 y stock restaurado.
- [ ] **CF-7:** `DELETE /products/{id}` → `is_active: false`, stock sin cambio, record consultable.
- [ ] **CF-8:** Arranque con BD nueva → 4–5 productos semilla cargados automáticamente.
- [ ] **CF-9:** `/docs` accesible y con todos los endpoints documentados.
- [ ] **CF-10:** Ninguna URL/puerto/key hardcodeada; todo proviene de `.env`.
- [ ] **CF-11:** Mensajes de error en español, identificadores en inglés (revisión manual).
- [ ] **CF-12:** `/reserve` y `/release` con transacción SQLite — fallo a mitad no deja inconsistencias.
- [ ] Actualizar `MEMORY.md` con la Fase 2 completada.
- [ ] Reportar resultado al desarrollador y esperar aprobación antes de continuar.

**Criterio de completado:** Los 12 CFs verificados; todos los tests pasan; `MEMORY.md` actualizado.

---

*Fin del plan de tareas — `servicio-inventario`. Total: 14 tareas · ~79 pruebas pytest.*
