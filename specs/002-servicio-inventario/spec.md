# Especificación — Servicio de Catálogo e Inventario

**Estado:** aprobada
**Versión:** 0.1.0
**Fecha:** 2026-11-21
**Autor:** Equipo SOA
**Servicio:** `servicio-inventario`
**Puerto:** 8002
**Base de datos:** `inventario.db` (SQLite aislada)

---

## 1. Contexto y Objetivo

El sistema de gestión de pedidos y entregas requiere un catálogo de productos con control de existencias en tiempo real. El `servicio-inventario` es el único responsable de registrar productos, mantener su disponibilidad y ejecutar operaciones atómicas de reserva y liberación de stock dentro de la arquitectura SOA.

**Objetivo principal:** Proveer una API REST autónoma que permita la gestión completa del ciclo de vida de un producto (CRUD) y que exponga operaciones transaccionales de inventario consumibles por `servicio-pedidos` para garantizar consistencia de stock durante el procesamiento de pedidos. El campo `weight_kg` de cada producto es además el insumo que `servicio-envios` necesita para calcular tarifas de entrega.

**Restricción arquitectónica clave:** Este servicio no importa código de ningún otro servicio. Toda comunicación hacia él ocurre exclusivamente por HTTP. Gestiona únicamente su propia base de datos `inventario.db`.

---

## 2. Actores

| Actor | Rol | Descripción |
|---|---|---|
| **Administrador** | Humano interno | Gestiona el catálogo: crea, actualiza, desactiva y reactiva productos a través de la API protegida. |
| **Agente externo (cliente web)** | Sistema frontend | Consulta el listado y detalle de productos para mostrarlos en la interfaz. |
| **Servicio Pedidos** | Sistema orquestador | Llama a los endpoints de reserva y liberación de stock al procesar o cancelar pedidos. |
| **Desarrollador / QA** | Humano técnico | Usa `/docs` y `/redoc` para explorar y probar la API durante el desarrollo. |

---

## 3. Historias de Usuario

### HU-01 — Registro de producto
> **Como** administrador,
> **quiero** registrar un nuevo producto con sus datos básicos (SKU, nombre, precio, peso y stock inicial),
> **para que** el sistema pueda incluirlo en pedidos y calcular tarifas de envío.

### HU-02 — Consulta individual
> **Como** administrador o agente externo,
> **quiero** consultar los datos completos de un producto por su identificador único,
> **para** verificar su información y disponibilidad actual antes de tomar una acción sobre él.

### HU-03 — Listado general con filtros
> **Como** administrador o agente externo,
> **quiero** obtener el listado paginado de todos los productos con filtro opcional por estado activo,
> **para** tener visibilidad del catálogo completo o solo de los productos disponibles.

### HU-04 — Actualización parcial de producto
> **Como** administrador,
> **quiero** modificar campos específicos de un producto existente,
> **para** mantener el catálogo actualizado ante cambios de precio, descripción o peso.

### HU-05 — Desactivación de producto
> **Como** administrador,
> **quiero** desactivar un producto sin eliminar su historial ni su stock,
> **para** retirarlo de la venta sin perder el registro ni afectar pedidos históricos.

### HU-06 — Reactivación de producto
> **Como** administrador,
> **quiero** reactivar un producto previamente desactivado,
> **para** que vuelva a estar disponible para nuevos pedidos.

### HU-07 — Reserva atómica de stock
> **Como** `servicio-pedidos`,
> **quiero** descontar el stock de uno o varios productos en una sola solicitud de forma atómica,
> **para** garantizar que nunca se procese un pedido con productos sin disponibilidad suficiente.

### HU-08 — Liberación de stock
> **Como** `servicio-pedidos`,
> **quiero** restaurar el stock de uno o varios productos cuando un pedido se cancela o falla,
> **para** que las unidades reservadas vuelvan a estar disponibles sin intervención manual.

### HU-09 — Validación de disponibilidad
> **Como** `servicio-pedidos`,
> **quiero** verificar si un conjunto de productos tiene stock suficiente sin descontarlo,
> **para** dar retroalimentación temprana al usuario antes de comprometer el inventario.

### HU-10 — Datos semilla iniciales
> **Como** desarrollador,
> **quiero** que el servicio inicie con productos de prueba precargados (si la BD está vacía),
> **para** poder explorar y probar la API sin necesidad de insertar datos manualmente.

---

## 4. Requisitos Funcionales

> Notación EARS: `CUANDO [disparador] EL SISTEMA [respuesta]` / `SI [condición] ENTONCES EL SISTEMA [consecuencia]`

### RF-1 — Inicialización y base de datos
**CUANDO** el servicio arranque por primera vez y la tabla de productos esté vacía,
**EL SISTEMA** deberá crear el esquema de la base de datos `inventario.db` y cargar automáticamente entre 4 y 5 productos de prueba con datos variados (distintos precios, pesos y niveles de stock).

**SI** la tabla ya contiene al menos un registro al arrancar,
**ENTONCES EL SISTEMA** no deberá ejecutar el proceso de seed y dejará los datos existentes intactos.

### RF-2 — Creación de producto
**CUANDO** el administrador envíe una solicitud `POST /products` con los datos requeridos y el header `X-API-Key` válido,
**EL SISTEMA** deberá validar que el `sku` no esté registrado previamente, persistir el nuevo producto con estado `is_active = true` y retornar los datos del producto creado con HTTP 201.

**SI** el `sku` ya existe en la base de datos (comparación insensible a mayúsculas),
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"Ya existe un producto registrado con ese SKU."*

**SI** algún campo requerido está ausente, `unit_price` ≤ 0, `weight_kg` ≤ 0, o `stock` < 0,
**ENTONCES EL SISTEMA** deberá retornar HTTP 422 con detalle de los campos inválidos.

### RF-3 — Consulta por ID
**CUANDO** cualquier actor envíe una solicitud `GET /products/{id}` con `X-API-Key` válido,
**EL SISTEMA** deberá retornar los datos completos del producto (incluido `is_active` y `stock` actual) con HTTP 200.

**SI** el `id` no corresponde a ningún producto registrado,
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Producto no encontrado."*

### RF-4 — Listado de productos
**CUANDO** cualquier actor envíe una solicitud `GET /products` con `X-API-Key` válido,
**EL SISTEMA** deberá retornar la lista paginada de productos, aceptando los parámetros opcionales `page` (entero ≥ 1, default 1), `page_size` (entero entre 1 y 100, default 20) e `is_active` (booleano, para filtrar por estado).

**SI** no se proporcionan parámetros de paginación,
**ENTONCES EL SISTEMA** deberá aplicar los valores por defecto y retornar HTTP 200 con la lista y metadatos de paginación (`total`, `page`, `page_size`, `total_pages`).

### RF-5 — Actualización parcial de producto
**CUANDO** el administrador envíe una solicitud `PATCH /products/{id}` con los campos a modificar y `X-API-Key` válido,
**EL SISTEMA** deberá actualizar únicamente los campos proporcionados (actualización parcial) y retornar el producto actualizado con HTTP 200.

**SI** el `id` no corresponde a ningún producto,
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Producto no encontrado."*

**SI** se intenta cambiar el `sku` a uno que ya pertenece a otro producto,
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"Ya existe un producto registrado con ese SKU."*

**SI** algún campo numérico proporcionado viola las restricciones (`unit_price` ≤ 0, `weight_kg` ≤ 0, `stock` < 0),
**ENTONCES EL SISTEMA** deberá retornar HTTP 422 con detalle de los campos inválidos.

### RF-6 — Desactivación de producto (borrado lógico)
**CUANDO** el administrador envíe una solicitud `DELETE /products/{id}` con `X-API-Key` válido,
**EL SISTEMA** deberá marcar el campo `is_active = false` en el registro del producto (el registro permanece en BD, el stock no se modifica) y retornar HTTP 200 con el producto actualizado.

**SI** el producto ya se encuentra inactivo (`is_active = false`),
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"El producto ya se encuentra inactivo."*

**SI** el `id` no corresponde a ningún producto,
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Producto no encontrado."*

### RF-7 — Reactivación de producto
**CUANDO** el administrador envíe una solicitud `PATCH /products/{id}/reactivate` con `X-API-Key` válido,
**EL SISTEMA** deberá establecer `is_active = true` en el registro del producto y retornar HTTP 200 con el producto actualizado.

**SI** el producto ya se encuentra activo,
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"El producto ya se encuentra activo."*

**SI** el `id` no corresponde a ningún producto,
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Producto no encontrado."*

### RF-8 — Reserva atómica de stock (descuento)
**CUANDO** `servicio-pedidos` envíe una solicitud `POST /products/reserve` con una lista de ítems (`product_id`, `quantity`) y `X-API-Key` válido,
**EL SISTEMA** deberá primero verificar, para **todos** los ítems de la lista, que cada producto exista, esté activo y tenga `stock >= quantity` solicitada.

**SI** todos los ítems pasan la validación,
**ENTONCES EL SISTEMA** deberá descontar atómicamente el stock de cada producto y retornar HTTP 200 con el stock resultante de cada ítem.

**SI** al menos un ítem falla (producto inexistente, inactivo o sin stock suficiente),
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 sin descontar ningún stock, indicando en el cuerpo de la respuesta qué productos fallaron y el motivo de cada falla (ej. *"Stock insuficiente para el producto ID 3: solicitado 5, disponible 2."*, *"El producto ID 7 está inactivo."*).

**SI** la lista de ítems está vacía,
**ENTONCES EL SISTEMA** deberá retornar HTTP 422 con el mensaje: *"La lista de productos a reservar no puede estar vacía."*

### RF-9 — Liberación/restauración de stock
**CUANDO** `servicio-pedidos` envíe una solicitud `POST /products/release` con una lista de ítems (`product_id`, `quantity`) y `X-API-Key` válido,
**EL SISTEMA** deberá sumar la `quantity` indicada al stock actual de cada producto, independientemente de si el producto está activo o inactivo, y retornar HTTP 200 con el stock resultante de cada ítem.

**SI** algún `product_id` de la lista no existe en la base de datos,
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 indicando qué IDs no fueron encontrados, sin modificar el stock de los demás.

**SI** la lista de ítems está vacía,
**ENTONCES EL SISTEMA** deberá retornar HTTP 422 con el mensaje: *"La lista de productos a liberar no puede estar vacía."*

### RF-10 — Consulta de disponibilidad sin descuento
**CUANDO** `servicio-pedidos` envíe una solicitud `POST /products/check-availability` con una lista de ítems (`product_id`, `quantity`) y `X-API-Key` válido,
**EL SISTEMA** deberá verificar para cada ítem si el producto existe, está activo y tiene stock suficiente, **sin modificar el stock**.

**EL SISTEMA** deberá retornar HTTP 200 con un arreglo indicando para cada ítem su disponibilidad (`available: true/false`) y, si no está disponible, la razón (stock insuficiente, producto inactivo o no encontrado).

### RF-11 — Protección con API Key
**CUANDO** cualquier actor envíe una solicitud a cualquier endpoint (excepto `GET /health`, `/docs` y `/redoc`),
**EL SISTEMA** deberá verificar la presencia y validez del header `X-API-Key`.

**SI** el header `X-API-Key` está ausente o su valor no coincide con la clave configurada en variables de entorno,
**ENTONCES EL SISTEMA** deberá retornar HTTP 401 con el mensaje: *"API Key inválida o no proporcionada."*

### RF-12 — Verificación de salud del servicio
**CUANDO** cualquier actor envíe una solicitud `GET /health` (sin autenticación),
**EL SISTEMA** deberá retornar HTTP 200 con un payload que indique el nombre del servicio, versión y estado `"ok"`.

---

## 5. Modelo de Datos — Entidad `Product`

> Solo se describe el QUÉ. El CÓMO (tipos SQLite, índices exactos) se define en la fase de implementación.

| Campo | Descripción | Restricciones |
|---|---|---|
| `id` | Identificador único autogenerado | Entero autoincremental, PK |
| `sku` | Código único de producto | Requerido, único en BD, no vacío, comparación insensible a mayúsculas |
| `name` | Nombre del producto | Requerido, no vacío, máx. 200 caracteres |
| `description` | Descripción del producto | Opcional, texto libre, máx. 1000 caracteres |
| `unit_price` | Precio unitario en la moneda del sistema | Requerido, decimal, > 0 |
| `weight_kg` | Peso en kilogramos (usado por servicio-envios) | Requerido, decimal, > 0 |
| `stock` | Unidades disponibles en inventario | Requerido, entero ≥ 0 |
| `is_active` | Estado del producto | Booleano, `true` por defecto al crear |
| `created_at` | Fecha y hora de creación | Autogenerado, solo lectura |
| `updated_at` | Fecha y hora de última modificación | Autogenerado, se actualiza en cada `PATCH` y operación de stock |

---

## 6. Requisitos No Funcionales

| ID | Requisito |
|---|---|
| **RNF-1** | El servicio debe exponer automáticamente `/docs` (Swagger UI) y `/redoc` generados por FastAPI. |
| **RNF-2** | Ninguna URL base, puerto ni valor de `X-API-Key` puede estar hardcodeado; deben leerse desde `.env` vía `python-dotenv`. |
| **RNF-3** | Todos los modelos de entrada y salida de la API deben estar definidos como clases Pydantic con validaciones explícitas. |
| **RNF-4** | Los mensajes de error al cliente deben estar redactados en español y ser descriptivos. |
| **RNF-5** | El servicio debe ser capaz de responder a solicitudes en menos de 500 ms bajo carga local normal. |
| **RNF-6** | La base de datos `inventario.db` debe persistir entre reinicios del servicio. |
| **RNF-7** | El servicio debe registrar (logs) al menos las solicitudes recibidas y los errores en consola, con nivel mínimo `INFO`. |
| **RNF-8** | Todo el código (variables, funciones, campos JSON y de BD) debe estar en inglés; solo los mensajes de error y la documentación van en español. |
| **RNF-9** | Las operaciones de reserva (`/reserve`) y liberación (`/release`) deben ejecutarse dentro de una transacción SQLite para garantizar atomicidad. |

---

## 7. Casos Límite

| Caso | Comportamiento esperado |
|---|---|
| `POST /products` con SKU duplicado (mayúsculas vs. minúsculas, ej. `PROD-01` vs. `prod-01`) | HTTP 409 — el sistema trata ambos como el mismo SKU. |
| `PATCH /products/{id}` con cuerpo vacío `{}` | HTTP 200 con el producto sin cambios (actualización parcial sin campos = no-op). |
| `GET /products` con `page_size=0` o `page_size=200` | HTTP 422 indicando que `page_size` debe estar entre 1 y 100. |
| `DELETE /products/{id}` sobre un producto ya inactivo | HTTP 409 — no se realiza ningún cambio adicional. |
| `PATCH /products/{id}/reactivate` sobre un producto ya activo | HTTP 409 — no se realiza ningún cambio adicional. |
| `DELETE /products/{id}` con `stock > 0` | HTTP 200 — se desactiva; el stock no se modifica. El orquestador es responsable de no reservar productos inactivos. |
| `POST /products/reserve` donde un ítem tiene `quantity = 0` | HTTP 422 — la cantidad a reservar debe ser ≥ 1. |
| `POST /products/reserve` con lista mixta (algunos con stock, otros sin stock) | HTTP 409 — rollback total; ningún stock se descuenta; la respuesta indica cada producto fallido y el motivo. |
| `POST /products/release` con `product_id` inexistente | HTTP 404 — no se modifica ningún otro ítem de la lista. |
| `POST /products/release` sobre un producto inactivo | HTTP 200 — el stock se restaura igualmente; la inactividad no bloquea la liberación. |
| `POST /products/check-availability` con lista vacía | HTTP 422 — la lista no puede estar vacía. |
| Valor de `id` no numérico en la URL (ej. `/products/abc`) | HTTP 422 — el sistema indica que el parámetro de ruta debe ser un entero. |
| BD vacía al listar (`GET /products`) | HTTP 200 con lista vacía `[]` y `total: 0`. |
| Seed automático cuando la BD ya tiene datos al reiniciar | El seed **no** debe ejecutarse; solo aplica cuando la tabla está completamente vacía. |

---

## 8. Fuera de Alcance

Los siguientes elementos quedan **explícitamente excluidos** de esta especificación:

- **Gestión de múltiples almacenes o ubicaciones:** El stock es un entero global por producto; no hay bodegas ni lotes.
- **Historial de movimientos de inventario:** No se lleva un log de entradas y salidas; solo se guarda el stock actual.
- **Stock mínimo y alertas de reabastecimiento:** No existe umbral mínimo ni notificaciones automáticas de bajo stock.
- **Categorías o familias de productos:** No hay taxonomía ni agrupamiento de productos.
- **Precios por volumen o descuentos:** `unit_price` es único e invariante por producto.
- **Eliminación física de registros:** No existe ningún endpoint que borre filas de la BD permanentemente.
- **Gestión de roles dentro del servicio:** Cualquier llamada con `X-API-Key` válida tiene acceso completo.
- **Versionado de la API (`/v1/`, `/v2/`):** La versión actual es la única; no hay infraestructura de versionado de rutas.
- **Integración con proveedores o sistemas ERP externos:** El servicio no se sincroniza con ninguna fuente de datos externa.
- **Imágenes o archivos adjuntos a productos:** Solo se manejan atributos de texto y números.

---

## 9. Criterios de Finalización (Definition of Done)

La especificación se considera **implementada y verificada** cuando:

- [x] **CF-1:** Existen pruebas `pytest` que cubren todos los requisitos funcionales (RF-1 a RF-12), incluyendo los casos límite de la sección 7, y todas pasan.
- [x] **CF-2:** El endpoint `GET /health` responde HTTP 200 sin `X-API-Key`.
- [x] **CF-3:** Todos los endpoints protegidos retornan HTTP 401 cuando se llaman sin `X-API-Key` o con clave incorrecta.
- [x] **CF-4:** `POST /products` con SKU duplicado (cualquier combinación de mayúsculas) retorna HTTP 409.
- [x] **CF-5:** `POST /products/reserve` con al menos un producto sin stock retorna HTTP 409 y **ningún** stock se descuenta (verificado consultando el stock de todos los productos involucrados antes y después).
- [x] **CF-6:** `POST /products/release` sobre un producto inactivo restaura el stock y retorna HTTP 200.
- [x] **CF-7:** `DELETE /products/{id}` produce borrado lógico; el registro sigue consultable por `GET /products/{id}` con `is_active = false` y el stock no cambia.
- [x] **CF-8:** El servicio arranca sin errores con una BD nueva y carga automáticamente 4–5 productos semilla.
- [x] **CF-9:** La documentación Swagger `/docs` está accesible y refleja todos los endpoints con sus respuestas documentadas.
- [x] **CF-10:** Ninguna URL, puerto ni clave está hardcodeada en el código; todo proviene de variables de entorno.
- [x] **CF-11:** El código pasa revisión manual verificando que los mensajes de error estén en español y los identificadores en inglés.
- [x] **CF-12:** Las operaciones `/reserve` y `/release` están protegidas por transacción SQLite; una falla a mitad de la lista no deja el stock en estado inconsistente.

---

*Fin de la especificación — Versión implementada y verificada satisfactoriamente (Fase 2 completada).*
