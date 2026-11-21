# Especificación — Servicio de Clientes

**Estado:** aprobada  
**Versión:** 0.1.0  
**Fecha:** 2026-11-20  
**Autor:** Equipo SOA  
**Servicio:** `servicio-clientes`  
**Puerto:** 8001  
**Base de datos:** `clientes.db` (SQLite aislada)

---

## 1. Contexto y Objetivo

El sistema de gestión de pedidos y entregas requiere un catálogo centralizado de clientes que sirva como fuente de verdad sobre quiénes pueden solicitar pedidos. El `servicio-clientes` es el único responsable de crear, consultar, actualizar y desactivar clientes dentro de la arquitectura SOA.

**Objetivo principal:** Proveer una API REST autónoma que permita la gestión completa del ciclo de vida de un cliente, y que exponga un endpoint de validación consumible por otros servicios (en particular `servicio-pedidos`) para verificar que un cliente existe y se encuentra activo antes de procesar cualquier pedido.

**Restricción arquitectónica clave:** Este servicio no importa código de ningún otro servicio. Toda comunicación hacia él ocurre exclusivamente por HTTP. Gestiona únicamente su propia base de datos `clientes.db`.

---

## 2. Actores

| Actor | Rol | Descripción |
|---|---|---|
| **Administrador** | Humano interno | Gestiona el catálogo: crea, actualiza, desactiva y reactiva clientes a través de la API protegida. |
| **Agente externo (cliente web)** | Sistema frontend | Consulta el listado y detalle de clientes mediante la interfaz web. |
| **Servicio Pedidos** | Sistema orquestador | Llama al endpoint de validación antes de registrar un pedido para un cliente. |
| **Desarrollador / QA** | Humano técnico | Usa `/docs` y `/redoc` para explorar y probar la API durante el desarrollo. |

---

## 3. Historias de Usuario

### HU-01 — Registro de cliente
> **Como** administrador,  
> **quiero** registrar un nuevo cliente con sus datos básicos,  
> **para que** la empresa pueda gestionarle pedidos y entregas.

### HU-02 — Consulta individual
> **Como** administrador o agente externo,  
> **quiero** consultar los datos completos de un cliente por su identificador único,  
> **para** verificar su información antes de tomar una acción sobre él.

### HU-03 — Listado general
> **Como** administrador o agente externo,  
> **quiero** obtener el listado paginado de todos los clientes (con filtros opcionales por estado),  
> **para** tener visibilidad del catálogo completo.

### HU-04 — Actualización de datos
> **Como** administrador,  
> **quiero** modificar los datos de un cliente existente,  
> **para** mantener la información actualizada ante cambios (teléfono, dirección, zona, etc.).

### HU-05 — Desactivación de cliente
> **Como** administrador,  
> **quiero** desactivar un cliente sin eliminar su historial,  
> **para** impedir que se le procesen nuevos pedidos sin perder el registro.

### HU-06 — Reactivación de cliente
> **Como** administrador,  
> **quiero** reactivar un cliente previamente desactivado,  
> **para** restablecer su capacidad de recibir pedidos cuando sea necesario.

### HU-07 — Validación para otros servicios
> **Como** `servicio-pedidos`,  
> **quiero** consultar si un cliente existe y está activo con una llamada HTTP simple,  
> **para** rechazar pedidos de clientes inexistentes o inactivos antes de procesarlos.

### HU-08 — Datos semilla iniciales
> **Como** desarrollador,  
> **quiero** que el servicio inicie con clientes de prueba precargados (si la BD está vacía),  
> **para** poder explorar y probar la API sin necesidad de insertar datos manualmente.

---

## 4. Requisitos Funcionales

> Notación EARS: `CUANDO [disparador] EL SISTEMA [respuesta]` / `SI [condición] ENTONCES EL SISTEMA [consecuencia]`

### RF-1 — Inicialización y base de datos
**CUANDO** el servicio arranque por primera vez y la tabla de clientes esté vacía,  
**EL SISTEMA** deberá crear el esquema de la base de datos `clientes.db` y cargar automáticamente entre 3 y 5 clientes de prueba con datos variados (distintas zonas y estados).

### RF-2 — Creación de cliente
**CUANDO** el administrador envíe una solicitud `POST /customers` con los datos requeridos y el header `X-API-Key` válido,  
**EL SISTEMA** deberá validar que el correo electrónico no esté registrado previamente, persistir el nuevo cliente con estado `is_active = true` y retornar los datos del cliente creado con HTTP 201.

**SI** el correo electrónico ya existe en la base de datos,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"Ya existe un cliente registrado con ese correo electrónico."*

**SI** algún campo requerido está ausente o no cumple el formato mínimo (ej. correo sin `@`),  
**ENTONCES EL SISTEMA** deberá retornar HTTP 422 con detalle de los campos inválidos.

### RF-3 — Consulta por ID
**CUANDO** cualquier actor envíe una solicitud `GET /customers/{id}` con `X-API-Key` válido,  
**EL SISTEMA** deberá retornar los datos completos del cliente (incluido `is_active`) con HTTP 200.

**SI** el `id` no corresponde a ningún cliente registrado,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Cliente no encontrado."*

### RF-4 — Listado de clientes
**CUANDO** cualquier actor envíe una solicitud `GET /customers` con `X-API-Key` válido,  
**EL SISTEMA** deberá retornar la lista paginada de clientes, aceptando los parámetros opcionales `page` (entero ≥ 1, default 1), `page_size` (entero entre 1 y 100, default 20) e `is_active` (booleano, para filtrar por estado).

**SI** no se proporcionan parámetros de paginación,  
**ENTONCES EL SISTEMA** deberá aplicar los valores por defecto y retornar HTTP 200 con la lista y metadatos de paginación (`total`, `page`, `page_size`, `total_pages`).

### RF-5 — Actualización de cliente
**CUANDO** el administrador envíe una solicitud `PATCH /customers/{id}` con los campos a modificar y `X-API-Key` válido,  
**EL SISTEMA** deberá actualizar únicamente los campos proporcionados (actualización parcial) y retornar el cliente actualizado con HTTP 200.

**SI** el `id` no corresponde a ningún cliente,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Cliente no encontrado."*

**SI** se intenta cambiar el correo electrónico a uno que ya pertenece a otro cliente,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"Ya existe un cliente registrado con ese correo electrónico."*

### RF-6 — Desactivación de cliente (borrado lógico)
**CUANDO** el administrador envíe una solicitud `DELETE /customers/{id}` con `X-API-Key` válido,  
**EL SISTEMA** deberá marcar el campo `is_active = false` en el registro del cliente (el registro permanece en BD) y retornar HTTP 200 con el cliente actualizado.

**SI** el cliente ya se encuentra inactivo (`is_active = false`),  
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"El cliente ya se encuentra inactivo."*

**SI** el `id` no corresponde a ningún cliente,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 404 con el mensaje: *"Cliente no encontrado."*

### RF-7 — Reactivación de cliente
**CUANDO** el administrador envíe una solicitud `PATCH /customers/{id}/reactivate` con `X-API-Key` válido,  
**EL SISTEMA** deberá establecer `is_active = true` en el registro del cliente y retornar HTTP 200 con el cliente actualizado.

**SI** el cliente ya se encuentra activo,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 409 con el mensaje: *"El cliente ya se encuentra activo."*

### RF-8 — Endpoint de validación para servicios externos
**CUANDO** `servicio-pedidos` (u otro servicio interno) envíe una solicitud `GET /customers/{id}/validate` con `X-API-Key` válido,  
**EL SISTEMA** deberá responder de la siguiente manera:  
- **HTTP 200** si el cliente existe y `is_active = true`.  
- **HTTP 404** si no existe ningún cliente con ese `id`.  
- **HTTP 409** si el cliente existe pero `is_active = false`, con el mensaje: *"El cliente existe pero se encuentra inactivo."*

### RF-9 — Protección con API Key
**CUANDO** cualquier actor envíe una solicitud a cualquier endpoint (excepto `/health`, `/docs` y `/redoc`),  
**EL SISTEMA** deberá verificar la presencia y validez del header `X-API-Key`.

**SI** el header `X-API-Key` está ausente o su valor no coincide con la clave configurada en variables de entorno,  
**ENTONCES EL SISTEMA** deberá retornar HTTP 401 con el mensaje: *"API Key inválida o no proporcionada."*

### RF-10 — Verificación de salud del servicio
**CUANDO** cualquier actor envíe una solicitud `GET /health` (sin autenticación),  
**EL SISTEMA** deberá retornar HTTP 200 con un payload que indique el nombre del servicio, versión y estado `"ok"`.

---

## 5. Modelo de Datos — Entidad `Customer`

> Solo se describe el QUÉ. El CÓMO (tipos SQLite, índices exactos) se define en la fase de implementación.

| Campo | Descripción | Restricciones |
|---|---|---|
| `id` | Identificador único autogenerado | Entero autoincremental, PK |
| `full_name` | Nombre completo del cliente | Requerido, no vacío, máx. 200 caracteres |
| `email` | Correo electrónico | Requerido, único en BD, debe contener `@` |
| `phone` | Teléfono de contacto | Requerido, texto libre, no vacío |
| `delivery_address` | Dirección de entrega | Requerido, no vacío, máx. 500 caracteres |
| `coverage_zone` | Zona de cobertura | Requerido, texto libre (ej. Local, Regional, Nacional) |
| `is_active` | Estado del cliente | Booleano, `true` por defecto al crear |
| `created_at` | Fecha y hora de creación | Autogenerado, solo lectura |
| `updated_at` | Fecha y hora de última modificación | Autogenerado, se actualiza en cada `PATCH` |

---

## 6. Requisitos No Funcionales

| ID | Requisito |
|---|---|
| **RNF-1** | El servicio debe exponer automáticamente `/docs` (Swagger UI) y `/redoc` generados por FastAPI. |
| **RNF-2** | Ninguna URL base, puerto ni valor de `X-API-Key` puede estar hardcodeado; deben leerse desde `.env` vía `python-dotenv`. |
| **RNF-3** | Todos los modelos de entrada y salida de la API deben estar definidos como clases Pydantic con validaciones explícitas. |
| **RNF-4** | Los mensajes de error al cliente deben estar redactados en español y ser descriptivos. |
| **RNF-5** | El servicio debe ser capaz de responder a solicitudes en menos de 500 ms bajo carga local normal (sin concurrencia extrema). |
| **RNF-6** | La base de datos `clientes.db` debe persistir entre reinicios del servicio. |
| **RNF-7** | El servicio debe registrar (logs) al menos las solicitudes recibidas y los errores en consola, con nivel mínimo `INFO`. |
| **RNF-8** | Todo el código (variables, funciones, campos JSON y de BD) debe estar en inglés; solo los mensajes de error y la documentación van en español. |

---

## 7. Casos Límite

| Caso | Comportamiento esperado |
|---|---|
| `POST /customers` con correo duplicado (mayúsculas vs. minúsculas) | El sistema debe tratar `Juan@mail.com` y `juan@mail.com` como el mismo correo (comparación insensible a mayúsculas). |
| `PATCH /customers/{id}` con cuerpo vacío `{}` | El sistema retorna HTTP 200 con el cliente sin cambios (actualización parcial sin campos = no-op). |
| `GET /customers` con `page_size=0` o `page_size=200` | El sistema retorna HTTP 422 indicando que `page_size` debe estar entre 1 y 100. |
| `DELETE /customers/{id}` sobre un cliente ya inactivo | HTTP 409 — no se realiza ningún cambio adicional. |
| `PATCH /customers/{id}/reactivate` sobre un cliente ya activo | HTTP 409 — no se realiza ningún cambio adicional. |
| Valor de `id` no numérico en la URL (ej. `/customers/abc`) | HTTP 422 — el sistema indica que el parámetro de ruta debe ser un entero. |
| BD vacía al listar (`GET /customers`) | HTTP 200 con lista vacía `[]` y `total: 0`. |
| Seed automático cuando la BD ya tiene datos al reiniciar | El seed **no** debe ejecutarse; solo aplica cuando la tabla está completamente vacía. |

---

## 8. Fuera de Alcance

Los siguientes elementos quedan **explícitamente excluidos** de esta especificación:

- **Autenticación de usuarios finales:** No hay login, sesiones ni JWT. La protección es únicamente por `X-API-Key` a nivel de servicio.
- **Paginación por cursor:** Solo se implementa paginación por offset (`page` / `page_size`).
- **Eliminación física de registros:** No existe ningún endpoint que borre filas de la BD permanentemente.
- **Gestión de roles dentro del servicio:** No se distingue entre tipos de administrador; cualquier llamada con `X-API-Key` válida tiene acceso completo.
- **Envío de correos electrónicos o notificaciones:** El servicio no emite ningún evento externo al crear o modificar clientes.
- **Integración con sistemas externos de CRM:** El servicio no se sincroniza con ninguna fuente de datos externa.
- **Versionado de la API (`/v1/`, `/v2/`):** La versión actual es la única; no hay infraestructura de versionado de rutas.
- **Historial de cambios de un cliente:** No se registra un log de auditoría de modificaciones; solo se guarda `updated_at`.

---

## 9. Criterios de Finalización (Definition of Done)

La especificación se considera **implementada y verificada** cuando:

- [ ] **CF-1:** Existen pruebas `pytest` que cubren todos los requisitos funcionales (RF-1 a RF-10), incluyendo los casos límite de la sección 7, y todas pasan.
- [ ] **CF-2:** El endpoint `GET /health` responde HTTP 200 sin `X-API-Key`.
- [ ] **CF-3:** Todos los endpoints protegidos retornan HTTP 401 cuando se llaman sin `X-API-Key` o con clave incorrecta.
- [ ] **CF-4:** `POST /customers` con correo duplicado (cualquier combinación de mayúsculas) retorna HTTP 409.
- [ ] **CF-5:** `GET /customers/{id}/validate` retorna 200, 404 o 409 según el estado del cliente.
- [ ] **CF-6:** `DELETE /customers/{id}` produce borrado lógico; el registro sigue consultable por `GET /customers/{id}`.
- [ ] **CF-7:** El servicio arranca sin errores con una BD nueva y carga automáticamente 3–5 clientes semilla.
- [ ] **CF-8:** La documentación Swagger `/docs` está accesible y refleja todos los endpoints con sus respuestas documentadas.
- [ ] **CF-9:** Ninguna URL, puerto ni clave está hardcodeada en el código; todo proviene de variables de entorno.
- [ ] **CF-10:** El código pasa revisión manual verificando que los mensajes de error estén en español y los identificadores en inglés.

---

*Fin de la especificación — versión borrador. Pendiente de aprobación antes de proceder al plan de implementación.*
