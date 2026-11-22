# Especificación — Servicio Orquestador de Pedidos

| Campo           | Valor                                       |
|-----------------|---------------------------------------------|
| **ID**          | SPEC-004                                    |
| **Servicio**    | servicio-pedidos                            |
| **Puerto**      | 8004                                        |
| **Base de datos** | `servicio-pedidos/pedidos.db` (SQLite aislada) |
| **Estado**      | aprobada                                    |
| **Versión**     | 0.1.0                                       |
| **Fecha**       | 2026-11-22                                  |
| **Autor**       | Equipo SOA                                  |

---

## 1. Contexto y Objetivo

El sistema SOA de Gestión de Pedidos y Entregas cuenta con tres servicios de dominio ya implementados y verificados:

| Servicio            | Puerto | Endpoints clave utilizados por el orquestador                          |
|---------------------|--------|------------------------------------------------------------------------|
| `servicio-clientes` | 8001   | `GET /customers/{id}/validate` → 200/404/409                          |
| `servicio-inventario` | 8002 | `POST /products/reserve` → 200/409; `POST /products/release` → 200/404 |
| `servicio-envios`   | 8003   | `POST /quote` → 200; `POST /shipments` → 201/409; `GET /shipments/{id}` → 200/404; `PATCH /shipments/{id}/status` → 200/409 |

`servicio-pedidos` es el **orquestador del flujo de negocio completo**: el único actor que coordina por HTTP los tres servicios anteriores para crear, consultar y cancelar pedidos de extremo a extremo. Tiene su propia base de datos `pedidos.db`, completamente aislada, donde persiste el estado canónico de cada pedido.

**Objetivo:** Proveer una API REST (`POST /orders`, `GET /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/cancel`) que implemente el flujo de negocio completo con garantías de consistencia eventual mediante el patrón Saga (compensación manual), resiliencia ante fallos de servicios externos y seguridad mediante `X-API-Key`.

---

## 2. Actores

| Actor                | Tipo       | Descripción                                                                      |
|----------------------|------------|----------------------------------------------------------------------------------|
| Cliente web          | Externo    | Frontend HTML/JS que consume esta API para crear y consultar pedidos.             |
| `servicio-clientes`  | Interno    | Valida que el cliente exista y esté activo; provee nombre y zona de envío.        |
| `servicio-inventario`| Interno    | Reserva y libera stock de productos.                                              |
| `servicio-envios`    | Interno    | Cotiza el costo de envío y gestiona el ciclo de vida de la guía de entrega.      |
| Administrador        | Externo    | Usuario con acceso a Swagger (`/docs`) para pruebas y diagnóstico.                |

---

## 3. Historias de Usuario

| ID    | Como…          | Quiero…                                                                              | Para…                                                            |
|-------|---------------|--------------------------------------------------------------------------------------|------------------------------------------------------------------|
| HU-01 | Cliente web   | Crear un pedido indicando mi ID de cliente y los productos que deseo                | Que el sistema valide mi cuenta, reserve el inventario y registre mi entrega automáticamente |
| HU-02 | Cliente web   | Consultar el detalle de un pedido con sus productos y el estado actual de mi entrega | Saber en qué punto del proceso se encuentra mi pedido             |
| HU-03 | Cliente web   | Ver el listado de mis pedidos paginado y filtrado por estado                         | Revisar mi historial de compras                                   |
| HU-04 | Cliente web   | Cancelar un pedido que aún no ha sido enviado                                        | Recuperar mi inversión antes de que salga a reparto               |
| HU-05 | Sistema       | Recibir un error claro (502/503) cuando un servicio externo esté caído              | Informar al cliente y registrar el fallo sin dejar inconsistencias |
| HU-06 | Sistema       | Que el inventario se libere automáticamente si falla la creación del envío           | Mantener la consistencia de stock sin intervención manual          |

---

## 4. Requisitos Funcionales

### RF-1 — Health Check

**CUANDO** el sistema recibe `GET /health`,  
**EL SISTEMA** responde `200 OK` con `{ "service": "servicio-pedidos", "status": "ok", "version": "0.1.0", "port": 8004 }` sin requerir autenticación.

---

### RF-2 — Autenticación por API Key

**CUANDO** el sistema recibe cualquier request a un endpoint distinto de `GET /health`,  
**SI** el header `X-API-Key` está ausente o su valor no coincide con la variable de entorno configurada,  
**EL SISTEMA** rechaza la petición con `401 Unauthorized` y el mensaje `"Clave de API inválida o ausente."` sin procesar la operación.

---

### RF-3 — Creación de Pedido (`POST /orders`)

**CUANDO** el sistema recibe `POST /orders` con body `{ "customer_id": <int>, "items": [{ "product_id": <int>, "quantity": <int> }, ...] }` y `X-API-Key` válida,  
**EL SISTEMA** ejecuta la siguiente secuencia orquestada:

**RF-3.1 — Validación de cliente**  
**SI** la llamada a `GET /customers/{customer_id}/validate` en `servicio-clientes` retorna `404`,  
**ENTONCES** el sistema responde `422 Unprocessable Entity` con mensaje `"El cliente no fue encontrado."` y aborta el proceso.

**SI** la llamada retorna `409` (cliente inactivo),  
**ENTONCES** el sistema responde `422 Unprocessable Entity` con mensaje `"El cliente existe pero se encuentra inactivo."` y aborta el proceso.

**RF-3.2 — Reserva de stock**  
**SI** la llamada a `POST /products/reserve` en `servicio-inventario` retorna `409` (stock insuficiente, producto inactivo o no encontrado),  
**ENTONCES** el sistema responde `422 Unprocessable Entity` propagando el detalle recibido del servicio de inventario y aborta el proceso.  
*(No hay stock descontado en este punto; no se requiere compensación.)*

**RF-3.3 — Cotización de envío**  
Usando la `coverage_zone` obtenida en RF-3.1, el sistema llama a `POST /quote` en `servicio-envios` para obtener el `shipping_cost`.  
**SI** esta llamada falla (timeout/conexión),  
**ENTONCES** el sistema ejecuta compensación (RF-3.6) y responde `502 Bad Gateway` con mensaje `"El servicio de cotización de envíos no está disponible."`.

**RF-3.4 — Persistencia del pedido**  
El sistema inserta el registro `order` y todos sus `order_items` en `pedidos.db` en una transacción atómica, calculando `total_amount = sum(unit_price × quantity) + shipping_cost`.  
**SI** la inserción en BD falla,  
**ENTONCES** el sistema ejecuta compensación (RF-3.6) y responde `500 Internal Server Error` con mensaje `"Error interno al persistir el pedido."`.

**RF-3.5 — Registro de guía de envío**  
Con el `order_id` recién generado, el sistema llama a `POST /shipments` en `servicio-envios` enviando `{ "order_id": <id>, "zone": <zone>, "recipient_name": <full_name> }`.  
**SI** esta llamada falla (timeout/conexión/409),  
**ENTONCES** el sistema ejecuta compensación (RF-3.6), elimina el registro del pedido de `pedidos.db` y responde `502 Bad Gateway` con mensaje `"No fue posible registrar la guía de envío."`.

**RF-3.6 — Compensación automática (Saga)**  
**CUANDO** el proceso de creación falla en los pasos RF-3.3, RF-3.4 o RF-3.5 (es decir, después de que el stock ya fue descontado en RF-3.2),  
**EL SISTEMA** llama a `POST /products/release` en `servicio-inventario` para liberar las cantidades reservadas.  
**SI** la llamada de compensación también falla,  
**ENTONCES** el sistema guarda el pedido (si ya fue persistido) con `status = FAILED` y `compensation_error = <descripción del fallo>`, y responde `500 Internal Server Error` con mensaje `"Error crítico: el pedido falló y la compensación de stock no pudo completarse. Requiere intervención manual."`.

**RF-3.7 — Respuesta exitosa**  
Completados todos los pasos sin error, el sistema responde `201 Created` con la representación completa del pedido (ver Modelo de Datos, §6) incluyendo `shipment_id` obtenido de `servicio-envios`.

**RF-3.8 — Validación de entrada**  
**SI** el body de la petición contiene `items` vacío (`[]`), `customer_id ≤ 0` o `quantity ≤ 0` en algún ítem,  
**ENTONCES** el sistema responde `422 Unprocessable Entity` con el detalle de validación de Pydantic.

---

### RF-4 — Consulta de Pedido (`GET /orders/{id}`)

**CUANDO** el sistema recibe `GET /orders/{id}` con `X-API-Key` válida,  
**SI** no existe ningún pedido con ese `id` en `pedidos.db`,  
**EL SISTEMA** responde `404 Not Found` con mensaje `"Pedido no encontrado."`.

**SI** el pedido existe,  
**EL SISTEMA** consulta el estado actual del envío en `servicio-envios` llamando a `GET /shipments/{shipment_id}` (si `shipment_id` no es nulo):

- **SI** la consulta a `servicio-envios` es exitosa, el sistema responde `200 OK` con todos los datos del pedido e incluye en los campos planos `shipment_status` con el estado devuelto por el servicio (ej. `"PENDING"`, `"IN_TRANSIT"`, `"DELIVERED"`, `"CANCELLED"`) y `"shipment_detail": null`.
- **SI** la consulta falla (timeout, conexión caída o error) o si `shipment_id` es nulo, el sistema responde `200 OK` con todos los datos del pedido e incluye `"shipment_status": null` y `"shipment_detail": "No disponible temporalmente"`; nunca bloquea la consulta del pedido por un fallo externo.

---

### RF-5 — Listado de Pedidos (`GET /orders`)

**CUANDO** el sistema recibe `GET /orders` con `X-API-Key` válida,  
**EL SISTEMA** retorna la lista paginada de pedidos almacenados en `pedidos.db` con los siguientes parámetros de query:

| Parámetro    | Tipo    | Por defecto | Descripción                                     |
|--------------|---------|-------------|-------------------------------------------------|
| `page`       | int ≥ 1 | 1           | Número de página                                |
| `page_size`  | int 1–100 | 20         | Registros por página                            |
| `status`     | string  | (ninguno)   | Filtrar por estado: `PENDING`, `CONFIRMED`, `CANCELLED`, `FAILED` |
| `customer_id`| int ≥ 1 | (ninguno)   | Filtrar por cliente                             |

La respuesta incluye `{ "items": [...], "total": <int>, "page": <int>, "page_size": <int>, "total_pages": <int> }`. Cada ítem es un resumen del pedido (sin `order_items` ni bloque completo de envío). El listado no consulta `servicio-envios`; usa solo datos de `pedidos.db`.

---

### RF-6 — Cancelación de Pedido (`PATCH /orders/{id}/cancel`)

**CUANDO** el sistema recibe `PATCH /orders/{id}/cancel` con `X-API-Key` válida,

**SI** el pedido no existe en `pedidos.db`,  
**ENTONCES** el sistema responde `404 Not Found` con mensaje `"Pedido no encontrado."`.

**SI** el pedido existe y su `status` es `CANCELLED` o `FAILED`,  
**ENTONCES** el sistema responde `409 Conflict` con mensaje `"El pedido no puede cancelarse porque ya está en estado terminal."`.

**SI** el pedido existe y su `status` es `CONFIRMED` (o `PENDING`), el sistema consulta el estado del envío en `servicio-envios` (`GET /shipments/{shipment_id}`):

- **SI** el estado del envío es `IN_TRANSIT` o `DELIVERED`,  
  **ENTONCES** el sistema responde `409 Conflict` con mensaje `"No se puede cancelar un pedido cuyo envío ya está en tránsito o entregado."` y no modifica ningún dato.

- **SI** el estado del envío es `PENDING`,  
  **ENTONCES** el sistema:
  1. Llama a `PATCH /shipments/{shipment_id}/status` con `{ "new_status": "CANCELLED" }` en `servicio-envios`.
  2. Llama a `POST /products/release` en `servicio-inventario` para liberar el stock.
  3. Actualiza el `status` del pedido a `CANCELLED` en `pedidos.db`.
  4. Responde `200 OK` con la representación actualizada del pedido.

**SI** la llamada a `servicio-envios` o `servicio-inventario` falla durante la cancelación,  
**ENTONCES** el sistema responde `502 Bad Gateway` indicando cuál servicio falló; el pedido **no** se marca como `CANCELLED` localmente (el estado permanece sin cambios para permitir reintentos).

**SI** el envío tiene `status = CANCELLED` (ya cancelado previamente),  
**ENTONCES** el sistema omite la llamada a `servicio-envios`, libera el stock igualmente y actualiza el pedido a `CANCELLED`.

---

### RF-7 — Resiliencia ante Fallos de Servicios Externos

**CUANDO** cualquier llamada HTTP a un servicio externo lanza `httpx.ConnectError`, `httpx.TimeoutException` u otro error de red,  
**EL SISTEMA** captura la excepción, registra el error en el log y retorna:
- `503 Service Unavailable` si el servicio externo está completamente inaccesible (sin respuesta).
- `502 Bad Gateway` si el servicio externo responde con un error 5xx inesperado.

Todos los clientes `httpx` tienen un **timeout configurable** mediante variable de entorno (`HTTP_TIMEOUT_SECONDS`, por defecto `10`).

---

## 5. Flujo de Orquestación — `POST /orders`

```
Cliente
  │
  ├─► [1] GET /customers/{id}/validate  ──► servicio-clientes (8001)
  │       └── 404/409 → 422; fallo red → 503
  │
  ├─► [2] POST /products/reserve        ──► servicio-inventario (8002)
  │       └── 409 → 422; fallo red → 503
  │
  ├─► [3] POST /quote                   ──► servicio-envios (8003)
  │       └── fallo → liberar stock [2] + 502
  │
  ├─► [4] INSERT order + order_items    ──► pedidos.db (local)
  │       └── fallo → liberar stock [2] + 500
  │
  └─► [5] POST /shipments               ──► servicio-envios (8003)
          └── fallo → liberar stock [2] + eliminar order [4] + 502
              └── si release falla → order.status = FAILED + 500 (intervención manual)

  Éxito total → 201 Created
```

---

## 6. Modelo de Datos

### Tabla `orders`

| Columna              | Tipo        | Restricciones               | Descripción                                                                        |
|----------------------|-------------|-----------------------------|-------------------------------------------------------------------------------------|
| `id`                 | INTEGER     | PK, AUTOINCREMENT           | Identificador único del pedido                                                     |
| `customer_id`        | INTEGER     | NOT NULL                    | ID del cliente (FK lógica a servicio-clientes; sin FK real entre servicios)        |
| `customer_name`      | TEXT        | NOT NULL                    | Nombre completo del cliente (snapshot en el momento del pedido)                    |
| `coverage_zone`      | TEXT        | NOT NULL                    | Zona de envío (`LOCAL`, `REGIONAL`, `NACIONAL`) snapshot del cliente               |
| `shipping_cost`      | REAL        | NOT NULL, ≥ 0               | Costo de envío cotizado al crear el pedido                                         |
| `total_amount`       | REAL        | NOT NULL, ≥ 0               | `sum(unit_price × quantity) + shipping_cost`                                       |
| `status`             | TEXT        | NOT NULL, DEFAULT `PENDING` | Estado del pedido: `PENDING`, `CONFIRMED`, `CANCELLED`, `FAILED`                   |
| `shipment_id`        | INTEGER     | NULLABLE                    | ID del registro en `servicio-envios` (nulo hasta que el envío se registre con éxito)|
| `compensation_error` | TEXT        | NULLABLE                    | Descripción del fallo de compensación si `status = FAILED`                        |
| `created_at`         | TEXT        | NOT NULL                    | Timestamp ISO-8601 UTC de creación                                                 |
| `updated_at`         | TEXT        | NOT NULL                    | Timestamp ISO-8601 UTC de última modificación                                      |

> [!NOTE]
> `status = PENDING` es el estado inicial durante la orquestación (antes de que se confirme el envío).
> `status = CONFIRMED` se establece una vez que `shipment_id` ha sido registrado exitosamente.
> Los estados `CANCELLED` y `FAILED` son terminales.

### Tabla `order_items`

| Columna        | Tipo    | Restricciones   | Descripción                                               |
|----------------|---------|-----------------|-----------------------------------------------------------|
| `id`           | INTEGER | PK, AUTOINCREMENT | Identificador único del ítem                            |
| `order_id`     | INTEGER | NOT NULL, FK → `orders.id` | Pedido al que pertenece                        |
| `product_id`   | INTEGER | NOT NULL        | ID del producto (referencia lógica a servicio-inventario) |
| `product_name` | TEXT    | NOT NULL        | Nombre del producto (snapshot al momento del pedido)      |
| `unit_price`   | REAL    | NOT NULL, > 0   | Precio unitario (snapshot al momento del pedido)          |
| `quantity`     | INTEGER | NOT NULL, > 0   | Cantidad reservada                                        |
| `subtotal`     | REAL    | NOT NULL, ≥ 0   | `unit_price × quantity`                                   |

> [!IMPORTANT]
> Los campos `customer_name`, `product_name` y `unit_price` son **snapshots** capturados en el momento de la creación del pedido. Cualquier cambio posterior en los servicios externos no altera los datos históricos del pedido.

### Esquemas JSON de Entrada y Salida

#### `POST /orders` — Request Body
```json
{
  "customer_id": 1,
  "items": [
    { "product_id": 3, "quantity": 2 },
    { "product_id": 7, "quantity": 1 }
  ]
}
```

#### `POST /orders` / `GET /orders/{id}` — Response (201 / 200)
```json
{
  "id": 1,
  "customer_id": 1,
  "customer_name": "Ana García",
  "coverage_zone": "LOCAL",
  "status": "CONFIRMED",
  "shipping_cost": 50.0,
  "total_amount": 350.0,
  "shipment_id": 12,
  "shipment_status": "PENDING",
  "shipment_detail": null,
  "compensation_error": null,
  "created_at": "2026-11-22T16:00:00",
  "updated_at": "2026-11-22T16:00:05",
  "items": [
    {
      "id": 1,
      "product_id": 3,
      "product_name": "Laptop Pro",
      "unit_price": 150.0,
      "quantity": 2,
      "subtotal": 300.0
    }
  ]
}
```

> [!NOTE]
> Cuando `servicio-envios` no está disponible en `GET /orders/{id}`, la respuesta incluye `"shipment_status": null` y `"shipment_detail": "No disponible temporalmente"`.

#### `GET /orders` — Response (200)
```json
{
  "items": [
    {
      "id": 1,
      "customer_id": 1,
      "customer_name": "Ana García",
      "coverage_zone": "LOCAL",
      "status": "CONFIRMED",
      "total_amount": 350.0,
      "shipment_id": 12,
      "created_at": "2026-11-22T16:00:00",
      "updated_at": "2026-11-22T16:00:05"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

## 7. Requisitos No Funcionales

| ID    | Categoría          | Descripción                                                                                                       |
|-------|--------------------|-----------------------------------------------------------------------------------------------------------------|
| RNF-1 | Independencia      | Sin imports cruzados entre servicios. Toda comunicación es HTTP REST mediante `httpx`.                           |
| RNF-2 | Aislamiento de BD  | `pedidos.db` es la única BD que gestiona `servicio-pedidos`; nunca accede a `clientes.db`, `inventario.db` ni `envios.db`. |
| RNF-3 | Configuración      | Todas las URLs de servicios externos, el `API_KEY` y `HTTP_TIMEOUT_SECONDS` se leen desde `.env` via `python-dotenv`; ningún valor hardcodeado en código. |
| RNF-4 | Resiliencia        | Todos los clientes `httpx` tienen timeout configurable (`HTTP_TIMEOUT_SECONDS`, default 10 s). `ConnectError` y `TimeoutException` se capturan siempre. |
| RNF-5 | Seguridad          | El header `X-API-Key` es obligatorio en todos los endpoints excepto `GET /health`. Respuesta `401` si ausente o inválida. |
| RNF-6 | Idioma             | Variables, funciones, clases, campos de BD y JSON en inglés. Mensajes de error al cliente, docstrings y comentarios en español. |
| RNF-7 | Atomicidad local   | La inserción de `orders` + `order_items` en `pedidos.db` ocurre en una sola transacción SQLite.                 |
| RNF-8 | Observabilidad     | Cada paso de orquestación (éxito y fallo) se registra con `logging` (nivel INFO/WARNING/ERROR).                 |
| RNF-9 | Paginación         | El listado `GET /orders` soporta `page` ≥ 1 y `page_size` entre 1 y 100.                                       |
| RNF-10 | Snapshots         | Los campos `customer_name`, `product_name` y `unit_price` en BD son snapshots inmutables del momento de la creación. |

---

## 8. Casos Límite

| ID   | Escenario                                                                                   | Comportamiento esperado                                                                 |
|------|---------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------|
| CL-1 | `items` vacío en `POST /orders`                                                             | `422` con mensaje de validación Pydantic                                                |
| CL-2 | `customer_id` o `product_id` ≤ 0                                                           | `422` con mensaje de validación Pydantic                                                |
| CL-3 | Producto duplicado en `items` (mismo `product_id` dos veces)                               | `422` con mensaje `"La lista de items contiene product_id duplicados."`                 |
| CL-4 | `servicio-clientes` caído al crear pedido                                                   | `503` con mensaje claro; sin reserva de stock                                           |
| CL-5 | `servicio-inventario` caído al crear pedido                                                 | `503` con mensaje claro; sin modificación de datos                                      |
| CL-6 | `servicio-envios` caído después de reservar stock                                           | Compensación automática (release); `502` al cliente                                     |
| CL-7 | Compensación de stock falla (servicio-inventario caído durante el release)                  | `status = FAILED`, `compensation_error` poblado; `500` al cliente                      |
| CL-8 | Cancelar pedido con envío `IN_TRANSIT`                                                      | `409` con mensaje "No se puede cancelar…"; pedido sin modificar                        |
| CL-9 | Cancelar pedido con envío `DELIVERED`                                                       | `409` con mensaje "No se puede cancelar…"; pedido sin modificar                        |
| CL-10 | Cancelar pedido con envío ya `CANCELLED`                                                   | Omite llamada a `servicio-envios`; libera stock; actualiza pedido a `CANCELLED`         |
| CL-11 | `GET /orders/{id}` con `servicio-envios` caído                                             | `200` con `shipment_status: null` y `shipment_detail: "No disponible temporalmente"`   |
| CL-12 | `GET /orders/{id}` para pedido con `status = FAILED` y `shipment_id = null`               | `200` devolviendo el pedido completo con `shipment_status: null`                        |
| CL-13 | Paginación más allá del total de registros                                                  | `200` con `items: []`, `total` real, `total_pages` calculado                           |
| CL-14 | Cancelar un pedido con `status = FAILED`                                                    | `409` con mensaje "El pedido no puede cancelarse porque ya está en estado terminal."    |

---

## 9. Fuera de Alcance

- Reintentos automáticos con backoff en llamadas HTTP (se delega a fase futura).
- Autenticación JWT o OAuth (sólo `X-API-Key` en esta fase).
- Notificaciones asíncronas (webhooks, colas de mensajes).
- Cache distribuida de estados de envío.
- Proceso de reconciliación automática para pedidos en estado `FAILED`.
- Modificación de un pedido ya creado (cambiar items o cliente).
- Gestión directa de clientes, productos o envíos desde este servicio.
- Base de datos semilla (`pedidos.db` arranca vacía; los datos de prueba los proveen los mocks de pytest).

---

## 10. Criterios de Finalización (CF)

| ID    | Criterio                                                                                                      |
|-------|--------------------------------------------------------------------------------------------------------------|
| CF-1  | `GET /health` responde `200 OK` sin `X-API-Key`.                                                            |
| CF-2  | Cualquier endpoint protegido sin `X-API-Key` válida responde `401`.                                          |
| CF-3  | `POST /orders` completa el flujo de 5 pasos exitosamente y responde `201` con el pedido completo.            |
| CF-4  | `POST /orders` con cliente inactivo o inexistente responde `422` y no reserva stock.                         |
| CF-5  | `POST /orders` con stock insuficiente responde `422` sin modificar pedidos.                                   |
| CF-6  | `POST /orders` dispara compensación automática si falla `servicio-envios` tras reservar stock y responde `502`. |
| CF-7  | Si la compensación también falla, el pedido queda con `status = FAILED` y `compensation_error` poblado.      |
| CF-8  | `GET /orders/{id}` devuelve `404` para pedido inexistente.                                                   |
| CF-9  | `GET /orders/{id}` devuelve `200` con `shipment_status: null` cuando `servicio-envios` no responde.          |
| CF-10 | `GET /orders` lista pedidos con paginación y filtros `status` / `customer_id`.                               |
| CF-11 | `PATCH /orders/{id}/cancel` cancela exitosamente un pedido con envío en `PENDING`.                           |
| CF-12 | `PATCH /orders/{id}/cancel` rechaza con `409` si el envío está `IN_TRANSIT` o `DELIVERED`.                  |
| CF-13 | `PATCH /orders/{id}/cancel` con envío ya `CANCELLED` libera el stock y actualiza el pedido localmente.       |
| CF-14 | Todos los errores de red (`ConnectError`, `TimeoutException`) se capturan y retornan `502` o `503`.          |
| CF-15 | Ninguna URL, clave ni secreto está hardcodeado en el código fuente.                                          |
| CF-16 | La suite de pruebas `pytest` cubre los CF-1 a CF-15 con mocks de los servicios externos.                     |
| CF-17 | `GET /docs` y `GET /redoc` son accesibles con la aplicación corriendo.                                       |
