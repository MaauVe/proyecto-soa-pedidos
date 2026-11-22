# Especificación — Servicio de Envíos

**Estado:** aprobada
**Versión:** 0.1.0
**Fecha:** 2026-11-22
**Autor:** Equipo SOA
**Servicio:** `servicio-envios`
**Puerto:** 8003
**Base de datos:** `envios.db` (SQLite aislada)

---

## 1. Contexto y Objetivo

El sistema de gestión de pedidos y entregas requiere un módulo capaz de calcular el costo de envío según la zona de destino y de registrar y hacer seguimiento del ciclo de vida de cada entrega. El `servicio-envios` es el único responsable de gestionar la lógica tarifaria y el estado de los envíos dentro de la arquitectura SOA.

**Objetivo principal:** Proveer una API REST autónoma que permita (1) cotizar el costo de un envío dado una zona de destino, y (2) crear y actualizar el estado de un registro de envío asociado a un pedido. `servicio-pedidos` es su principal consumidor; lo llama vía HTTP para obtener tarifas y para registrar y avanzar el estado de cada envío durante la orquestación.

**Restricción arquitectónica clave:** Este servicio no importa código de ningún otro servicio. Toda comunicación hacia él ocurre exclusivamente por HTTP. Gestiona únicamente su propia base de datos `envios.db`. Las zonas (`LOCAL`, `REGIONAL`, `NACIONAL`) y sus tarifas son constantes de la aplicación cargadas desde variables de entorno.

---

## 2. Actores

| Actor | Rol | Descripción |
|---|---|---|
| **Servicio Pedidos** | Sistema orquestador | Actor principal: cotiza envíos, crea registros y avanza su estado durante la orquestación de pedidos. |
| **Administrador** | Humano interno | Puede consultar y actualizar el estado de un envío directamente vía API protegida cuando sea necesario. |
| **Agente externo (cliente web)** | Sistema frontend | Consulta el detalle de un envío para mostrar el estado de entrega al usuario final. |
| **Desarrollador / QA** | Humano técnico | Usa `/docs` y `/redoc` para explorar y probar la API durante el desarrollo. |

---

## 3. Historias de Usuario

### HU-01 — Cotización de envío
> **Como** `servicio-pedidos`,
> **quiero** conocer el costo de envío para una zona de destino específica,
> **para** incluirlo en el resumen del pedido antes de confirmar la compra al usuario.

### HU-02 — Consulta de zonas disponibles
> **Como** `servicio-pedidos` o administrador,
> **quiero** obtener la lista de zonas de envío disponibles con sus tarifas actuales,
> **para** validar la zona elegida por el cliente antes de cotizar.

### HU-03 — Creación de registro de envío
> **Como** `servicio-pedidos`,
> **quiero** crear un registro de envío vinculado a un pedido al momento de confirmar la compra,
> **para** tener trazabilidad de la entrega desde su inicio.

### HU-04 — Consulta de envío por ID
> **Como** administrador o agente externo,
> **quiero** consultar los datos completos de un envío por su identificador único,
> **para** conocer su estado actual y detalles de entrega.

### HU-05 — Listado de envíos
> **Como** administrador,
> **quiero** obtener el listado paginado de todos los envíos con filtro opcional por estado,
> **para** tener visibilidad operativa de las entregas en curso y completadas.

### HU-06 — Avance de estado de envío
> **Como** administrador o `servicio-pedidos`,
> **quiero** actualizar el estado de un envío siguiendo la secuencia permitida,
> **para** reflejar el progreso real de la entrega en el sistema.

### HU-07 — Cancelación de envío
> **Como** `servicio-pedidos`,
> **quiero** cancelar un envío en estado `PENDING` o `IN_TRANSIT` cuando el pedido asociado falla o es cancelado,
> **para** que el registro refleje la situación real sin dejar envíos huérfanos activos.

### HU-08 — Verificación de salud del servicio
> **Como** desarrollador o sistema de monitoreo,
> **quiero** consultar un endpoint público que confirme que el servicio está operativo,
> **para** incluirlo en chequeos de disponibilidad sin necesidad de autenticación.

---

## 4. Requisitos Funcionales

> Notación EARS: `CUANDO [disparador] EL SISTEMA [respuesta]` / `SI [condiciÃ³n] ENTONCES EL SISTEMA [consecuencia]`

### RF-1 — Inicialización y base de datos
**CUANDO** el servicio arranque, **EL SISTEMA** debe crear la tabla `shipments` en `envios.db` si no existe, aplicando todas las restricciones de integridad definidas en el modelo de datos, y quedar listo para aceptar peticiones.

**SI** la tabla ya existe al arrancar, **ENTONCES EL SISTEMA** no debe alterarla ni eliminar registros existentes.

### RF-2 — Salud del servicio (`GET /health`)
**CUANDO** cualquier cliente realice `GET /health` sin ningún header de autenticación, **EL SISTEMA** debe responder HTTP 200 con un JSON que incluya `status: "ok"`, el nombre del servicio y la versión.

**SI** la base de datos no es accesible en ese momento, **ENTONCES EL SISTEMA** debe responder HTTP 503 con `status: "error"` e indicar el motivo en español.

### RF-3 — Consulta de zonas disponibles (`GET /zones`)
**CUANDO** un cliente autenticado realice `GET /zones`, **EL SISTEMA** debe responder HTTP 200 con la lista de las tres zonas (`LOCAL`, `REGIONAL`, `NACIONAL`) y la tarifa plana asociada a cada una, tal como estén configuradas en las variables de entorno `RATE_LOCAL`, `RATE_REGIONAL` y `RATE_NACIONAL`.

### RF-4 — Cotización de envío (`POST /quote`)
**CUANDO** un cliente autenticado realice `POST /quote` con un campo `zone` válido, **EL SISTEMA** debe responder HTTP 200 con la zona solicitada y el costo de envío (`shipping_cost`) correspondiente según la tarifa configurada en `.env`.

**SI** el campo `zone` enviado no corresponde a ninguna de las zonas válidas (`LOCAL`, `REGIONAL`, `NACIONAL`), **ENTONCES EL SISTEMA** debe responder HTTP 422 indicando en español las zonas aceptadas.

### RF-5 — Creación de envío (`POST /shipments`)
**CUANDO** un cliente autenticado realice `POST /shipments` con `order_id`, `zone` válida y `recipient_name`, **EL SISTEMA** debe crear un nuevo registro de envío con estado inicial `PENDING`, registrar la tarifa vigente al momento de la creación (`shipping_cost`) y responder HTTP 201 con el recurso creado completo.

**SI** ya existe un envío con el mismo `order_id`, **ENTONCES EL SISTEMA** debe responder HTTP 409 indicando en español que ya existe un envío para ese pedido.

**SI** `zone` no es válida, **ENTONCES EL SISTEMA** debe responder HTTP 422 indicando las zonas aceptadas en español.

### RF-6 — Consulta de envío por ID (`GET /shipments/{id}`)
**CUANDO** un cliente autenticado realice `GET /shipments/{id}`, **EL SISTEMA** debe responder HTTP 200 con todos los campos del envío: `id`, `order_id`, `zone`, `recipient_name`, `shipping_cost`, `status`, `created_at` y `updated_at`.

**SI** el `id` no corresponde a ningún registro existente, **ENTONCES EL SISTEMA** debe responder HTTP 404 con un mensaje descriptivo en español.

### RF-7 — Listado de envíos (`GET /shipments`)
**CUANDO** un cliente autenticado realice `GET /shipments`, **EL SISTEMA** debe responder HTTP 200 con una lista paginada de envíos, aceptando los parámetros opcionales `page` (≥ 1, default 1), `page_size` (entre 1 y 100, default 20), `status` (filtro exacto por estado) y `order_id` (filtro exacto por ID de pedido).

**SI** `status` no es un valor válido del enum (`PENDING`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED`), **ENTONCES EL SISTEMA** debe responder HTTP 422 indicando los valores aceptados en español.

### RF-8 — Actualización de estado (`PATCH /shipments/{id}/status`)
**CUANDO** un cliente autenticado realice `PATCH /shipments/{id}/status` con un `new_status` válido, **EL SISTEMA** debe actualizar el estado del envío solo si la transición es permitida según la máquina de estados definida y responder HTTP 200 con el envío actualizado completo.

**Las transiciones permitidas son:**
- `PENDING → IN_TRANSIT`
- `PENDING → CANCELLED`
- `IN_TRANSIT → DELIVERED`
- `IN_TRANSIT → CANCELLED`

**SI** la transición solicitada no está en la lista de transiciones permitidas (ej. `DELIVERED → IN_TRANSIT`, `CANCELLED → PENDING`), **ENTONCES EL SISTEMA** debe responder HTTP 409 indicando en español el estado actual y las transiciones válidas desde él.

**SI** el `id` no corresponde a ningún registro existente, **ENTONCES EL SISTEMA** debe responder HTTP 404 con un mensaje descriptivo en español.

**SI** el envío ya se encuentra en estado `DELIVERED` o `CANCELLED` (estados terminales), **ENTONCES EL SISTEMA** debe responder HTTP 409 indicando que el envío está en un estado final y no puede ser modificado.

### RF-9 — Protección de endpoints con `X-API-Key`
**CUANDO** cualquier cliente realice una petición a cualquier endpoint excepto `GET /health`, **EL SISTEMA** debe exigir el header `X-API-Key` con el valor configurado en la variable de entorno `API_KEY`.

**SI** el header está ausente o su valor es incorrecto, **ENTONCES EL SISTEMA** debe responder HTTP 401 con el header `WWW-Authenticate: X-API-Key` y un mensaje descriptivo en español.

### RF-10 — Documentación automática
**CUANDO** el servicio esté en ejecución, **EL SISTEMA** debe exponer la documentación interactiva de la API en `/docs` (Swagger UI) y `/redoc` (ReDoc), reflejando todos los endpoints con sus esquemas de solicitud, respuesta y códigos HTTP posibles.

---

## 5. Modelo de Datos

### Tabla `shipments`

| Campo | Tipo SQL | Restricciones | Descripción |
|---|---|---|---|
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Identificador único del envío. |
| `order_id` | `INTEGER` | `NOT NULL UNIQUE` | ID del pedido asociado en `servicio-pedidos`. |
| `zone` | `TEXT` | `NOT NULL CHECK(zone IN ('LOCAL','REGIONAL','NACIONAL'))` | Zona de destino del envío. |
| `recipient_name` | `TEXT` | `NOT NULL` | Nombre del destinatario. |
| `shipping_cost` | `REAL` | `NOT NULL CHECK(shipping_cost >= 0)` | Tarifa vigente en el momento de creación. |
| `status` | `TEXT` | `NOT NULL DEFAULT 'PENDING' CHECK(status IN ('PENDING','IN_TRANSIT','DELIVERED','CANCELLED'))` | Estado actual del envío. |
| `created_at` | `TEXT` | `NOT NULL DEFAULT (datetime('now'))` | Timestamp ISO-8601 de creación (UTC). |
| `updated_at` | `TEXT` | `NOT NULL DEFAULT (datetime('now'))` | Timestamp ISO-8601 de última modificación (UTC). |

### Máquina de estados

```
PENDING ──→ IN_TRANSIT ──→ DELIVERED (terminal)
   │              │
   └──────────────┴──→ CANCELLED (terminal)
```

### Variables de entorno requeridas (`.env` raíz)

| Variable | Ejemplo | Uso |
|---|---|---|
| `API_KEY` | `changeme-local-key` | Header `X-API-Key` para autenticación. |
| `PORT_ENVIOS` | `8003` | Puerto de escucha del servicio. |
| `RATE_LOCAL` | `50` | Tarifa plana zona LOCAL (MXN). |
| `RATE_REGIONAL` | `100` | Tarifa plana zona REGIONAL (MXN). |
| `RATE_NACIONAL` | `200` | Tarifa plana zona NACIONAL (MXN). |

> No se guarda una tabla de zonas en BD. Las tarifas se leen de `.env` en cada arranque.

---

## 6. Requisitos No Funcionales

| ID | Requisito |
|---|---|
| **RNF-1** | Todos los modelos de entrada y salida usan Pydantic v2 con validación estricta. |
| **RNF-2** | Los handlers son funciones síncronas (`def`); no se usa `async def`. |
| **RNF-3** | La base de datos usa `sqlite3` nativo; no se usa ORM externo. |
| **RNF-4** | No existe ningún `requirements.txt` propio del servicio; se reutiliza el de la raíz del proyecto. |
| **RNF-5** | La configuración se carga con `python-dotenv` usando `find_dotenv()` apuntando al `.env` raíz. |
| **RNF-6** | Los mensajes de error al cliente están en español; los identificadores de código, campos JSON y endpoints, en inglés. |
| **RNF-7** | Ninguna URL, puerto, clave ni tarifa está hardcodeada en el código fuente. |
| **RNF-8** | El servicio responde en menos de 500 ms para cualquier operación bajo condiciones normales de carga local. |
| **RNF-9** | La documentación Swagger en `/docs` describe todos los endpoints con sus esquemas y códigos HTTP posibles. |
| **RNF-10** | Las pruebas `pytest` se consolidan en 2 archivos: `tests/test_base_auth.py` y `tests/test_shipments.py`. |

---

## 7. Casos Límite

| Situación | Comportamiento esperado |
|---|---|
| `POST /quote` con `zone` en minúsculas (ej. `"local"`) | HTTP 422 — solo se aceptan valores en mayúsculas; la respuesta indica las zonas válidas en español. |
| `POST /shipments` con `order_id` duplicado | HTTP 409 — no se crea un segundo registro; la respuesta indica en español que ya existe un envío para ese pedido. |
| `PATCH /shipments/{id}/status` con `new_status = "DELIVERED"` sobre un envío `CANCELLED` | HTTP 409 — el envío está en estado terminal; la respuesta indica las transiciones válidas (ninguna). |
| `PATCH /shipments/{id}/status` con `new_status` igual al estado actual (ej. `PENDING → PENDING`) | HTTP 409 — la transición no es válida; el sistema indica el estado actual y las transiciones permitidas. |
| `GET /shipments/{id}` con `id` no numérico (ej. `/shipments/abc`) | HTTP 422 — el parámetro de ruta debe ser un entero. |
| `GET /shipments` con `page_size=0` o `page_size=200` | HTTP 422 — `page_size` debe estar entre 1 y 100. |
| `GET /shipments` sin registros en BD | HTTP 200 con lista vacía `[]` y `total: 0`. |
| `GET /shipments?status=ENVIADO` (estado inválido) | HTTP 422 — el filtro solo acepta los cuatro estados del enum. |
| `PATCH /shipments/{id}/status` con `id` inexistente | HTTP 404 — no se realiza ninguna modificación; la respuesta describe el error en español. |
| `RATE_LOCAL`, `RATE_REGIONAL` o `RATE_NACIONAL` no definidas en `.env` | El servicio no arranca y emite un mensaje de error claro indicando la variable faltante. |
| `POST /shipments` con `recipient_name` vacío (`""`) o solo espacios | HTTP 422 — el campo no puede estar vacío ni contener solo espacios en blanco. |

---

## 8. Fuera de Alcance

Los siguientes elementos quedan **explícitamente excluidos** de esta especificación:

- **Cálculo tarifario por peso:** La tarifa es plana por zona; el campo `weight_kg` de los productos lo gestiona `servicio-inventario` y no interviene aquí.
- **Seguimiento GPS o coordenadas:** No hay geolocalización ni dirección física; solo zona de destino.
- **Notificaciones push/email:** El servicio no emite ningún tipo de alerta o notificación al cambiar de estado.
- **Historial de cambios de estado:** Solo se conserva el estado actual; no hay tabla de auditoría de transiciones.
- **CRUD de zonas:** Las zonas son constantes definidas en el código y en `.env`; no son gestionables por API.
- **Integración con proveedores externos de mensajería:** El servicio es autónomo; no conecta con APIs de paquetería externas.
- **Eliminación física de envíos:** No existe ningún endpoint `DELETE /shipments/{id}`. La cancelación se hace mediante cambio de estado.
- **Autenticación por roles:** Cualquier portador de `X-API-Key` válida tiene acceso completo; no hay distinción de roles.
- **Paginación de zonas:** Solo existen tres zonas; `GET /zones` devuelve siempre la lista completa sin paginación.

---

## 9. Criterios de Finalización (Definition of Done)

La especificación se considera **implementada y verificada** cuando:

- [ ] **CF-1:** Existen pruebas `pytest` que cubren todos los requisitos funcionales (RF-1 a RF-10), incluyendo los casos límite de la sección 7, y todas pasan.
- [ ] **CF-2:** El endpoint `GET /health` responde HTTP 200 sin `X-API-Key`.
- [ ] **CF-3:** Todos los endpoints protegidos retornan HTTP 401 cuando se llaman sin `X-API-Key` o con clave incorrecta.
- [ ] **CF-4:** `POST /quote` con zona inválida retorna HTTP 422 con mensaje en español.
- [ ] **CF-5:** `POST /shipments` con `order_id` duplicado retorna HTTP 409 sin crear un segundo registro.
- [ ] **CF-6:** `PATCH /shipments/{id}/status` con transición inválida retorna HTTP 409 indicando el estado actual y las transiciones permitidas.
- [ ] **CF-7:** `PATCH /shipments/{id}/status` con transición válida actualiza el estado y retorna HTTP 200 con el recurso completo.
- [ ] **CF-8:** Un envío en estado terminal (`DELIVERED` o `CANCELLED`) rechaza cualquier cambio de estado con HTTP 409.
- [ ] **CF-9:** `GET /zones` retorna las tres zonas con sus tarifas leídas de `.env` y responde HTTP 200.
- [ ] **CF-10:** La documentación Swagger `/docs` está accesible y refleja todos los endpoints con sus respuestas documentadas.
- [ ] **CF-11:** Ninguna URL, puerto, clave ni tarifa está hardcodeada en el código; todo proviene de variables de entorno.
- [ ] **CF-12:** El código pasa revisión manual verificando que los mensajes de error estén en español y los identificadores en inglés.

---

*Fin de la especificación — Estado: borrador. Pendiente de revisión y aprobación.*
