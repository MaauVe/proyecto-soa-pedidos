# tasks.md — Plan de Implementación: Servicio de Clientes

**Fase:** 1 — `servicio-clientes`  
**Spec de referencia:** `specs/001-servicio-clientes/spec.md` (aprobada)  
**Puerto:** 8001 | **BD:** `clientes.db`

> Regla SDD: una tarea a la vez. No iniciar la siguiente sin aprobación explícita.  
> Orden obligatorio por tarea: **Prueba pytest → Implementación → pytest pasa → Stop → Aprobación**

---

## Estado de las Tareas

| ID | Tarea | RF cubiertos | Estado |
|---|---|---|---|
| T-01 | Estructura base del proyecto | — | ✅ Completada |
| T-02 | Modelo de datos y BD (SQLite + seed) | RF-1 | ✅ Completada |
| T-03 | Autenticación X-API-Key + /health | RF-9, RF-10 | ✅ Completada |
| T-04 | Crear cliente (POST /customers) | RF-2 | ✅ Completada |
| T-05 | Consulta por ID (GET /customers/{id}) | RF-3 | ⬜ Pendiente |
| T-06 | Listado paginado (GET /customers) | RF-4 | ⬜ Pendiente |
| T-07 | Actualización parcial (PATCH /customers/{id}) | RF-5 | ⬜ Pendiente |
| T-08 | Desactivación lógica (DELETE /customers/{id}) | RF-6 | ⬜ Pendiente |
| T-09 | Reactivación (PATCH /customers/{id}/reactivate) | RF-7 | ⬜ Pendiente |
| T-10 | Endpoint de validación (GET /customers/{id}/validate) | RF-8 | ⬜ Pendiente |
| T-11 | Revisión final, casos límite y criterios de finalización | CF-1 a CF-10 | ⬜ Pendiente |

---

## Detalle de cada Tarea

### T-01 — Estructura base del proyecto ✅
**Objetivo:** Crear el esqueleto del servicio con todas las dependencias declaradas.

> **Ajuste aprobado:** No se crean `requirements.txt` ni `.env.example` propios; el servicio
> usa los de la raíz del proyecto. `clientes.db` se almacena dentro de `servicio-clientes/`.

**Entregables:**
- `servicio-clientes/`
  - `main.py` — app FastAPI mínima con `/health` operativo
  - `config.py` — carga variables de entorno desde la raíz con `find_dotenv()`
  - `README.md` — instrucciones de arranque del servicio
  - `tests/__init__.py` — paquete de pruebas vacío

**Criterio de done:** `uvicorn main:app --port 8001` arranca sin errores; `/health` retorna 200 y `/docs` es accesible.

---

### T-02 — Modelo de datos y BD (SQLite + seed)
**Objetivo:** Definir la tabla `customers` y la lógica de inicialización con datos semilla.  
**RF cubierto:** RF-1

**Entregables:**
- `servicio-clientes/database.py` — engine SQLAlchemy, sesión y función `init_db()`
- `servicio-clientes/models.py` — modelo SQLAlchemy `Customer` (9 campos de la spec)
- `servicio-clientes/seed.py` — función `seed_customers()` que inserta 3–5 clientes solo si la tabla está vacía
- `servicio-clientes/tests/test_seed.py` — prueba que verifica: seed corre en BD vacía, NO corre si ya hay datos

**Criterio de done:** `pytest tests/test_seed.py` pasa en verde.

---

### T-03 — Autenticación X-API-Key + /health
**Objetivo:** Implementar el middleware/dependencia de autenticación y el endpoint de salud.  
**RF cubiertos:** RF-9, RF-10

**Entregables:**
- `servicio-clientes/auth.py` — dependencia FastAPI que valida el header `X-API-Key`
- Endpoint `GET /health` (sin auth) → `{"service": "servicio-clientes", "version": "0.1.0", "status": "ok"}`
- `servicio-clientes/tests/test_auth.py` — pruebas:
  - `/health` retorna 200 sin API Key
  - Cualquier endpoint protegido retorna 401 sin API Key
  - Cualquier endpoint protegido retorna 401 con API Key incorrecta
  - Endpoint protegido retorna respuesta esperada con API Key correcta

**Criterio de done:** `pytest tests/test_auth.py` pasa en verde.

---

### T-04 — Crear cliente (POST /customers)
**Objetivo:** Implementar el endpoint de creación con validaciones de unicidad de correo.  
**RF cubierto:** RF-2

**Entregables:**
- `servicio-clientes/schemas.py` — `CustomerCreate`, `CustomerResponse` (Pydantic)
- Endpoint `POST /customers` en `main.py` (o router dedicado)
- `servicio-clientes/tests/test_create_customer.py` — pruebas:
  - Creación exitosa → HTTP 201 con todos los campos
  - Correo duplicado (exacto) → HTTP 409
  - Correo duplicado (distinta capitalización) → HTTP 409
  - Campos requeridos ausentes → HTTP 422
  - Correo sin `@` → HTTP 422

**Criterio de done:** `pytest tests/test_create_customer.py` pasa en verde.

---

### T-05 — Consulta por ID (GET /customers/{id})
**Objetivo:** Implementar la lectura de un cliente por su ID.  
**RF cubierto:** RF-3

**Entregables:**
- Endpoint `GET /customers/{id}` en `main.py`
- `servicio-clientes/tests/test_get_customer.py` — pruebas:
  - ID existente (activo) → HTTP 200 con datos correctos
  - ID existente (inactivo) → HTTP 200 con `is_active: false`
  - ID inexistente → HTTP 404
  - ID no numérico (`/customers/abc`) → HTTP 422

**Criterio de done:** `pytest tests/test_get_customer.py` pasa en verde.

---

### T-06 — Listado paginado (GET /customers)
**Objetivo:** Implementar el listado con paginación y filtro por estado.  
**RF cubierto:** RF-4

**Entregables:**
- Endpoint `GET /customers` con query params: `page`, `page_size`, `is_active`
- `servicio-clientes/schemas.py` — `CustomerList` con metadatos (`total`, `page`, `page_size`, `total_pages`)
- `servicio-clientes/tests/test_list_customers.py` — pruebas:
  - Sin parámetros → HTTP 200, paginación por defecto (page=1, page_size=20)
  - Filtro `is_active=true` → solo activos
  - Filtro `is_active=false` → solo inactivos
  - BD vacía → HTTP 200, lista vacía, `total: 0`
  - `page_size=0` → HTTP 422
  - `page_size=200` → HTTP 422

**Criterio de done:** `pytest tests/test_list_customers.py` pasa en verde.

---

### T-07 — Actualización parcial (PATCH /customers/{id})
**Objetivo:** Implementar la actualización parcial de campos de un cliente.  
**RF cubierto:** RF-5

**Entregables:**
- `servicio-clientes/schemas.py` — `CustomerUpdate` (todos los campos opcionales)
- Endpoint `PATCH /customers/{id}` en `main.py`
- `servicio-clientes/tests/test_update_customer.py` — pruebas:
  - Actualización de un campo → HTTP 200, solo ese campo cambia
  - Cuerpo vacío `{}` → HTTP 200, cliente sin cambios (no-op)
  - Cambio de email a uno ya existente en otro cliente → HTTP 409
  - ID inexistente → HTTP 404
  - `updated_at` se modifica tras actualización exitosa

**Criterio de done:** `pytest tests/test_update_customer.py` pasa en verde.

---

### T-08 — Desactivación lógica (DELETE /customers/{id})
**Objetivo:** Implementar el borrado lógico que marca `is_active = false`.  
**RF cubierto:** RF-6

**Entregables:**
- Endpoint `DELETE /customers/{id}` en `main.py`
- `servicio-clientes/tests/test_deactivate_customer.py` — pruebas:
  - Cliente activo → HTTP 200, `is_active: false`, registro sigue en BD
  - `GET /customers/{id}` después de DELETE → sigue retornando HTTP 200
  - Cliente ya inactivo → HTTP 409
  - ID inexistente → HTTP 404

**Criterio de done:** `pytest tests/test_deactivate_customer.py` pasa en verde.

---

### T-09 — Reactivación (PATCH /customers/{id}/reactivate)
**Objetivo:** Implementar el endpoint para reactivar clientes inactivos.  
**RF cubierto:** RF-7

**Entregables:**
- Endpoint `PATCH /customers/{id}/reactivate` en `main.py`
- `servicio-clientes/tests/test_reactivate_customer.py` — pruebas:
  - Cliente inactivo → HTTP 200, `is_active: true`
  - Cliente ya activo → HTTP 409
  - ID inexistente → HTTP 404

**Criterio de done:** `pytest tests/test_reactivate_customer.py` pasa en verde.

---

### T-10 — Endpoint de validación (GET /customers/{id}/validate)
**Objetivo:** Implementar el endpoint de consulta semántica para servicios externos.  
**RF cubierto:** RF-8

**Entregables:**
- Endpoint `GET /customers/{id}/validate` en `main.py`
- **HTTP 200** retorna JSON con: `id`, `full_name`, `coverage_zone`, `delivery_address`, `is_active`
- `servicio-clientes/tests/test_validate_customer.py` — pruebas:
  - Cliente existente y activo → HTTP 200 con campos `id`, `full_name`, `coverage_zone`, `delivery_address`, `is_active`
  - ID inexistente → HTTP 404
  - Cliente existente pero inactivo → HTTP 409
  - Sin API Key → HTTP 401

**Criterio de done:** `pytest tests/test_validate_customer.py` pasa en verde.

---

### T-11 — Revisión final y criterios de finalización
**Objetivo:** Ejecutar la suite completa, verificar todos los CF de la spec y revisar calidad de código.

**Acciones:**
- `pytest servicio-clientes/tests/ -v` → todos en verde
- Verificar que `/docs` lista todos los endpoints con respuestas documentadas
- Revisar que ningún string hardcodea URL, puerto ni clave
- Verificar que todos los mensajes de error están en español
- Verificar que todos los identificadores (variables, funciones, campos) están en inglés
- Actualizar `MEMORY.md` con el estado de Fase 1 completada

**Criterio de done:** Todos los CF-1 a CF-10 de la spec están marcados ✅ y el desarrollador da aprobación.

---

## Tarea Actual

> 🔵 **Siguiente: T-05 — Consulta por ID (GET /customers/{id})**  
> T-04 completada y verificada (10/10 tests T-04, suite acumulada 38/38). Esperando aprobación para iniciar T-05.
