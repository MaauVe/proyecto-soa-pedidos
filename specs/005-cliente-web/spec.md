# Especificación — Cliente Web (Frontend HTML/CSS/JS puro)

| Campo             | Valor                                           |
|-------------------|-------------------------------------------------|
| **ID**            | SPEC-005                                        |
| **Servicio**      | cliente-web                                     |
| **Puerto**        | N/A (servido localmente via `python -m http.server`) |
| **Base de datos** | N/A (sin estado; consume APIs de los 4 servicios) |
| **Estado**        | aprobada                                        |
| **Versión**       | 0.1.0                                           |
| **Fecha**         | 2026-11-22                                      |
| **Autor**         | Equipo SOA                                      |

---

## 1. Contexto y Objetivo

El sistema SOA cuenta con cuatro microservicios completamente implementados y verificados:

| Servicio              | Puerto | Rol                                      |
|-----------------------|--------|------------------------------------------|
| `servicio-clientes`   | 8001   | Gestión de clientes y validación         |
| `servicio-inventario` | 8002   | Gestión de productos y reservas de stock |
| `servicio-envios`     | 8003   | Cotización, registro y seguimiento de guías |
| `servicio-pedidos`    | 8004   | Orquestador del flujo de pedidos (Saga)  |

`cliente-web` es el **frontend HTML/CSS/JS puro** que permite a un operador humano interactuar con los cuatro servicios desde el navegador, sin necesidad de usar Swagger ni herramientas de línea de comandos.

**Objetivo:** Proveer una Single-Page Application (SPA) minimalista implementada en un único `index.html` con CSS y JS propios (sin frameworks ni dependencias NPM), que permita administrar clientes, inventario, pedidos y envíos desde una interfaz navegable por tabs/secciones, usando `fetch()` con el header `X-API-Key` para comunicarse con los 4 servicios.

---

## 2. Actores

| Actor          | Tipo    | Descripción                                                                      |
|----------------|---------|----------------------------------------------------------------------------------|
| Operador web   | Externo | Usuario humano con acceso al navegador que administra el sistema SOA             |
| `servicio-clientes`  | Interno | Proveedor de datos de clientes (puerto 8001)                               |
| `servicio-inventario` | Interno | Proveedor de datos de inventario (puerto 8002)                            |
| `servicio-envios`    | Interno | Proveedor de datos de guías de envío (puerto 8003)                         |
| `servicio-pedidos`   | Interno | Proveedor de datos de pedidos y orquestador (puerto 8004)                  |

---

## 3. Historias de Usuario

| ID    | Como…          | Quiero…                                                                                   | Para…                                                             |
|-------|----------------|-------------------------------------------------------------------------------------------|-------------------------------------------------------------------|
| HU-01 | Operador web   | Ver el estado de salud de los 4 servicios en un Dashboard                                | Saber si todos los servicios están activos antes de operar        |
| HU-02 | Operador web   | Listar, crear, ver detalle, activar y desactivar clientes                                 | Administrar el catálogo de clientes del sistema                   |
| HU-03 | Operador web   | Listar productos del inventario, crear uno nuevo y editar su stock/precio                 | Mantener actualizado el inventario disponible para pedidos        |
| HU-04 | Operador web   | Crear un nuevo pedido seleccionando cliente y productos con cantidades                    | Iniciar el flujo de negocio completo desde el frontend            |
| HU-05 | Operador web   | Listar pedidos y ver el detalle de cada uno, incluyendo estado del envío                 | Monitorear el estado de todos los pedidos del sistema             |
| HU-06 | Operador web   | Cancelar un pedido activo desde el frontend                                               | Corregir pedidos erróneos antes de que salgan a reparto           |
| HU-07 | Operador web   | Listar guías de envío y ver el detalle de cada una                                       | Rastrear el estado de las entregas                                |
| HU-08 | Operador web   | Cambiar manualmente el estado de una guía de envío (`PENDING → IN_TRANSIT → DELIVERED`)  | Simular el avance del proceso de entrega en el entorno local      |
| HU-09 | Operador web   | Recibir mensajes de error claros en español cuando una operación falla                   | Entender qué ocurrió sin revisar la consola del navegador         |

---

## 4. Requisitos Funcionales

### RF-1 — Estructura SPA y Navegación

**CUANDO** el operador accede a `index.html`,  
**EL SISTEMA** muestra una interfaz de una sola página con navegación por secciones visibles mediante tabs o sidebar. Las secciones disponibles son:

| Sección      | Contenido principal                                |
|--------------|----------------------------------------------------|
| Dashboard    | Estado de salud de los 4 servicios                 |
| Clientes     | Tabla de clientes + formulario de creación + acciones |
| Inventario   | Tabla de productos + formulario de creación/edición |
| Pedidos      | Formulario de nuevo pedido + tabla de pedidos + detalle |
| Envíos       | Tabla de guías + detalle + cambio de estado        |

**CUANDO** el operador hace clic en un tab/sección,  
**EL SISTEMA** muestra esa sección y oculta las demás **sin recargar la página**.

---

### RF-2 — Configuración de API y URLs

**CUANDO** el frontend realiza cualquier llamada a un servicio,  
**EL SISTEMA** usa las URLs base y la `API_KEY` definidas en un archivo `config.js` separado (importado por `index.html`) con la siguiente estructura:

```js
const CONFIG = {
  API_KEY: "changeme-local-key",
  URL_CLIENTES:   "http://localhost:8001",
  URL_INVENTARIO: "http://localhost:8002",
  URL_ENVIOS:     "http://localhost:8003",
  URL_PEDIDOS:    "http://localhost:8004"
};
```

Toda llamada `fetch()` incluye el header `X-API-Key: <CONFIG.API_KEY>` y `Content-Type: application/json`.

---

### RF-3 — Dashboard: Estado de los Servicios

**CUANDO** el operador activa la sección Dashboard (o al cargar la página por primera vez),  
**EL SISTEMA** llama a `GET /health` en los 4 servicios en paralelo y muestra para cada uno:

- Nombre del servicio y puerto.
- Indicador visual de estado: `✅ Activo` (si responde 200) o `❌ Caído` (si falla o responde error).
- Versión y estado devueltos en el JSON de `/health`.

**SI** cualquier servicio no responde (error de red o timeout),  
**ENTONCES** el indicador muestra `❌ Caído` sin bloquear la carga de los demás.

---

### RF-4 — Sección Clientes

#### RF-4.1 — Listar clientes

**CUANDO** el operador activa la sección Clientes,  
**EL SISTEMA** llama a `GET /customers` en `servicio-clientes` y muestra una tabla con columnas: ID, Nombre completo, Email, Zona de cobertura, Estado (activo/inactivo), Acciones. (Extrae `data.items` del objeto paginado de respuesta).

#### RF-4.2 — Crear cliente

**CUANDO** el operador completa el formulario de creación (Nombre completo, Email, Teléfono, Dirección, Zona de cobertura) y hace clic en **Crear**,  
**EL SISTEMA** llama a `POST /customers` y, si es exitoso, recarga la tabla de clientes y muestra un mensaje de confirmación.  
**SI** el servidor responde error, el sistema muestra el mensaje de error en español recibido del servicio.

#### RF-4.3 — Ver detalle de cliente

**CUANDO** el operador hace clic en el ID de un cliente en la tabla,  
**EL SISTEMA** llama a `GET /customers/{id}` y muestra un panel/modal con todos los campos del cliente.

#### RF-4.4 — Desactivar cliente

**CUANDO** el operador hace clic en **Desactivar** en la fila de un cliente activo,  
**EL SISTEMA** llama a `DELETE /customers/{id}` (desactivación lógica) y recarga la tabla.

#### RF-4.5 — Reactivar cliente

**CUANDO** el operador hace clic en **Reactivar** en la fila de un cliente inactivo,  
**EL SISTEMA** llama a `PATCH /customers/{id}/reactivate` y recarga la tabla.

---

### RF-5 — Sección Inventario

#### RF-5.1 — Listar productos

**CUANDO** el operador activa la sección Inventario,  
**EL SISTEMA** llama a `GET /products` en `servicio-inventario` y muestra una tabla con columnas: ID, SKU, Nombre, Precio unitario, Stock disponible, Peso (kg), Estado, Acciones. (Extrae `data.items` del objeto paginado de respuesta).

#### RF-5.2 — Crear producto

**CUANDO** el operador completa el formulario de creación (SKU, Nombre, Descripción, Precio, Stock inicial, Peso en kg) y hace clic en **Crear**,  
**EL SISTEMA** llama a `POST /products` y recarga la tabla si es exitoso.

#### RF-5.3 — Editar producto

**CUANDO** el operador hace clic en **Editar** en la fila de un producto,  
**EL SISTEMA** muestra un formulario pre-poblado con los datos actuales del producto (SKU, Nombre, Descripción, Precio, Stock disponible, Peso en kg).  
**CUANDO** el operador confirma los cambios,  
**EL SISTEMA** llama a `PATCH /products/{id}` y recarga la tabla.

---

### RF-6 — Sección Pedidos

#### RF-6.1 — Listar pedidos

**CUANDO** el operador activa la sección Pedidos,  
**EL SISTEMA** llama a `GET /orders` en `servicio-pedidos` y muestra una tabla con columnas: ID, Cliente, Zona, Total, Estado, ID Envío, Fecha creación, Acciones. (Extrae `data.items` del objeto paginado de respuesta).

#### RF-6.2 — Ver detalle de pedido

**CUANDO** el operador hace clic en el ID de un pedido en la tabla,  
**EL SISTEMA** llama a `GET /orders/{id}` y muestra un panel/modal con:
- Datos del pedido (cliente, zona, costo envío, total, estado, fechas).
- Lista de items (producto, cantidad, precio unitario, subtotal).
- Estado del envío (`shipment_status`, `shipment_detail` si aplica).

#### RF-6.3 — Crear pedido

**CUANDO** el operador activa el sub-panel "Nuevo Pedido",  
**EL SISTEMA** muestra un formulario con:
- Selector `<select>` poblado dinámicamente con clientes activos (`GET /customers`).
- Sección dinámica para agregar items: cada item cuenta con un selector `<select>` poblado dinámicamente con productos disponibles (`GET /products`) y campo `quantity` (número); el operador puede agregar múltiples items con un botón **+ Agregar producto** y eliminar filas individuales.
- Botón **Crear Pedido**.

**CUANDO** el operador hace clic en **Crear Pedido**,  
**EL SISTEMA** llama a `POST /orders` con el body construido y recarga la tabla si responde 201.  
**SI** el servidor responde error, el sistema muestra el mensaje de error en español.

#### RF-6.4 — Cancelar pedido

**CUANDO** el operador hace clic en **Cancelar** en la fila de un pedido con estado `CONFIRMED` o `PENDING`,  
**EL SISTEMA** pide confirmación mediante un diálogo nativo del navegador (`confirm()`).  
**SI** el operador confirma, el sistema llama a `PATCH /orders/{id}/cancel` y recarga la tabla.  
**SI** el servidor responde error (ej. 409), el sistema muestra el mensaje de error en español.

---

### RF-7 — Sección Envíos

#### RF-7.1 — Listar guías de envío

**CUANDO** el operador activa la sección Envíos,  
**EL SISTEMA** llama a `GET /shipments` en `servicio-envios` y muestra una tabla con columnas: ID, ID Pedido, Destinatario, Zona, Estado, Fecha creación, Acciones. (Extrae `data.items` del objeto paginado de respuesta).

#### RF-7.2 — Ver detalle de guía

**CUANDO** el operador hace clic en el ID de una guía en la tabla,  
**EL SISTEMA** llama a `GET /shipments/{id}` y muestra un panel/modal con todos los campos de la guía.

#### RF-7.3 — Cambiar estado de guía

**CUANDO** el operador hace clic en **Cambiar Estado** en la fila de una guía no terminal,  
**EL SISTEMA** muestra un selector con los estados válidos disponibles (`PENDING → IN_TRANSIT`, `IN_TRANSIT → DELIVERED`, o `PENDING → CANCELLED`) y un botón **Confirmar**.  
**CUANDO** el operador confirma,  
**EL SISTEMA** llama a `PATCH /shipments/{id}/status` con `{ "new_status": "<estado>" }` y recarga la tabla.

---

### RF-8 — Manejo de Errores en la UI

**CUANDO** cualquier llamada `fetch()` falla (error de red, timeout o respuesta de error HTTP),  
**EL SISTEMA** muestra un mensaje de error visible en la sección activa con el texto recibido del campo `detail` del body JSON de error (o un mensaje genérico en español si el body no es JSON).  
El mensaje de error desaparece automáticamente tras 5 segundos o cuando el usuario interactúa con la sección.

**SI** la respuesta es `401 Unauthorized`,  
**EL SISTEMA** muestra: `"Error de autenticación: verifica la API Key en config.js."`.

---

## 5. Estructura de Archivos

```
cliente-web/
├── index.html      # Único archivo HTML: estructura base, tabs, secciones, referencias a JS/CSS
├── config.js       # Constantes de configuración: API_KEY y URLs de los 4 servicios
├── styles.css      # Hoja de estilos propia (sin frameworks)
└── app.js          # Lógica SPA completa: navegación, llamadas fetch(), renderizado DOM
```

> [!NOTE]
> No se requiere servidor backend ni bundler. El frontend se sirve con `python -m http.server 5500` desde la carpeta `cliente-web/` (o directamente abriendo `index.html` en el navegador, con CORS habilitado en los servicios backend).

> [!IMPORTANT]
> `config.js` NO debe incluirse en el repositorio Git si contiene claves reales. Para el proyecto universitario local, se acepta hardcodear `"changeme-local-key"` como valor por defecto en `config.js`.

---

## 6. Requisitos No Funcionales

| ID     | Categoría       | Descripción                                                                                                       |
|--------|-----------------|-------------------------------------------------------------------------------------------------------------------|
| RNF-1  | Tecnología      | HTML5, CSS3 y JavaScript ES6+ puros. Sin frameworks JS (React, Vue, etc.) ni CSS (Bootstrap, Tailwind). Sin npm. |
| RNF-2  | SPA             | Una sola página HTML. La navegación entre secciones no recarga la página; se logra con `display: none/block` en JS. |
| RNF-3  | Configuración   | URLs y API Key definidas exclusivamente en `config.js`. Ningún valor hardcodeado en `app.js` o `index.html`.     |
| RNF-4  | Autenticación   | Toda llamada `fetch()` incluye el header `X-API-Key` tomado de `CONFIG.API_KEY`.                                 |
| RNF-5  | Responsividad   | La interfaz es funcional en pantallas de escritorio (≥ 1024px de ancho). No se requiere diseño mobile.           |
| RNF-6  | Idioma          | Todos los textos visibles al usuario (labels, botones, mensajes, placeholders) están en **español**.              |
| RNF-7  | Feedback visual | Toda operación asíncrona muestra un indicador de carga (spinner o texto "Cargando…") mientras espera la respuesta. |
| RNF-8  | Legibilidad     | El código JS es modular: cada sección del SPA tiene sus propias funciones agrupadas y comentadas en español.      |
| RNF-9  | CORS            | Los servicios backend ya tienen CORS configurado para aceptar peticiones desde `localhost`. El frontend no necesita proxy. |

---

## 7. Casos Límite

| ID   | Escenario                                                                                   | Comportamiento esperado en la UI                                                            |
|------|---------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| CL-1 | Servicio caído al cargar el Dashboard                                                       | Indicador `❌ Caído` para ese servicio; los demás se muestran normalmente                   |
| CL-2 | Tabla de clientes/productos/pedidos/envíos vacía                                            | Mensaje "No hay registros disponibles." en lugar de tabla vacía                             |
| CL-3 | Formulario de nuevo pedido sin items                                                        | El botón **Crear Pedido** está deshabilitado hasta que haya al menos 1 item                |
| CL-4 | Error 422 al crear pedido (cliente inactivo, stock insuficiente)                            | Mensaje de error con el `detail` recibido del servicio en español                          |
| CL-5 | Error 409 al cancelar pedido (envío en tránsito)                                            | Mensaje de error claro; el pedido permanece en la tabla sin cambios                        |
| CL-6 | Error 401 en cualquier llamada                                                              | Mensaje "Error de autenticación: verifica la API Key en config.js."                        |
| CL-7 | Pedido con `shipment_status: null` en el detalle                                            | Muestra "No disponible temporalmente" en el campo de estado de envío                       |
| CL-8 | Intentar cambiar estado de una guía terminal (`DELIVERED` o `CANCELLED`)                    | Botón **Cambiar Estado** deshabilitado o ausente para esas guías                           |
| CL-9 | Error de red (servicio completamente inaccesible) en cualquier operación                   | Mensaje "No se pudo conectar con el servicio. Verifica que esté ejecutándose."             |

---

## 8. Fuera de Alcance

- Autenticación de usuario (login, sesión, JWT). Se asume que el operador conoce la API Key.
- Diseño responsive para dispositivos móviles.
- Pruebas automatizadas con `pytest`, Jest, Cypress u otras herramientas (la verificación es manual).
- Funcionalidades de exportación (PDF, CSV) de tablas.
- Paginación de tablas en el frontend (se muestra lo que devuelva el backend con sus parámetros por defecto).
- Búsqueda o filtros avanzados en la UI (más allá de los que provee el backend).
- Gestión directa de zonas de envío o tarifas.
- Notificaciones en tiempo real (WebSockets, SSE).
- Gestión de múltiples API Keys o usuarios.

---

## 9. Criterios de Finalización (CF)

| ID    | Criterio                                                                                                                      |
|-------|-------------------------------------------------------------------------------------------------------------------------------|
| CF-1  | `index.html` carga en el navegador sin errores en la consola.                                                                |
| CF-2  | La navegación entre las 5 secciones (Dashboard, Clientes, Inventario, Pedidos, Envíos) funciona sin recarga de página.       |
| CF-3  | El Dashboard muestra el estado real de los 4 servicios (activos o caídos) consultando `GET /health`.                         |
| CF-4  | La tabla de Clientes lista los clientes existentes; el formulario de creación agrega uno nuevo correctamente.                 |
| CF-5  | Las acciones Desactivar y Reactivar de un cliente funcionan y la tabla se actualiza.                                          |
| CF-6  | La tabla de Inventario lista los productos; el formulario de creación agrega uno nuevo.                                      |
| CF-7  | El formulario de edición de producto pre-carga los datos actuales y guarda los cambios con `PATCH`.                          |
| CF-8  | El formulario de nuevo pedido permite agregar y eliminar items dinámicamente.                                                |
| CF-9  | `POST /orders` desde el frontend crea un pedido correctamente y la tabla se recarga.                                         |
| CF-10 | El detalle de pedido muestra los items y el estado del envío (o "No disponible temporalmente" si el servicio falla).         |
| CF-11 | La cancelación de un pedido funciona y la tabla se recarga; los errores 409 se muestran en español.                          |
| CF-12 | La tabla de Envíos lista las guías; el detalle muestra todos los campos de la guía.                                          |
| CF-13 | El cambio de estado de una guía funciona y la tabla se recarga; guías terminales no muestran el botón de cambio.             |
| CF-14 | Todos los errores HTTP (400, 401, 404, 409, 422, 502, 503) muestran un mensaje legible en español en la UI.                  |
| CF-15 | El indicador de carga ("Cargando…") se muestra durante las llamadas `fetch()` y desaparece al recibir la respuesta.         |
| CF-16 | Ninguna URL ni API Key está hardcodeada fuera de `config.js`.                                                                |
