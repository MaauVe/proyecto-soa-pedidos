# Plan de Tareas — Cliente Web (`cliente-web`)

**Spec de referencia:** `specs/005-cliente-web/spec.md` (aprobada ✅)  
**Archivos:** `cliente-web/index.html`, `cliente-web/config.js`, `cliente-web/styles.css`, `cliente-web/app.js`

> **Regla SDD:** Una tarea a la vez. Verificación manual al final de cada bloque antes de continuar.  
> Los bloques definen puntos de parada obligatorios (`🛑`).

> [!NOTE]
> `cliente-web` no tiene lógica de servidor ni pruebas `pytest`. La verificación se realiza abriendo `index.html` en el navegador (o con `python -m http.server 5500` en la carpeta `cliente-web/`) con los 4 servicios corriendo.
> **Importante:** Los endpoints de listado (`GET /customers`, `GET /products`, `GET /orders`, `GET /shipments`) devuelven respuestas paginadas con estructura `{ "items": [...], "total": ... }`, por lo que `app.js` siempre debe acceder a `data.items`.

---

## Estado de las Tareas

| ID   | Tarea                                                               | RF / CF cubiertos               | Estado         |
|------|---------------------------------------------------------------------|---------------------------------|----------------|
| T-23 | Estructura base: `index.html`, `config.js`, `styles.css`, `app.js` | RF-1, RF-2, RNF-1–4             | ✅ Completada  |
| T-24 | Dashboard: estado de salud de los 4 servicios                       | RF-3, CF-3                      | ✅ Completada  |
| T-25 | Sección Clientes: listar, crear, desactivar, reactivar              | RF-4, CF-4, CF-5                | ✅ Completada  |
| T-26 | Sección Inventario: listar, crear, editar                           | RF-5, CF-6, CF-7                | ✅ Completada  |
| T-27 | Sección Pedidos: listar, crear, ver detalle, cancelar               | RF-6, CF-8–11                   | ✅ Completada  |
| T-28 | Sección Envíos: listar, ver detalle, cambiar estado                 | RF-7, CF-12, CF-13              | ⬜ Pendiente   |
| T-29 | Manejo de errores global y feedback visual (spinners)               | RF-8, CF-14, CF-15              | ⬜ Pendiente   |
| T-30 | Verificación de Criterios de Finalización (CF-1 a CF-16)            | Todos los CF                    | ⬜ Pendiente   |

---

## Bloque 1 — Estructura base y navegación SPA

### T-23 — Estructura base del frontend y habilitación de CORS

**RF cubiertos:** RF-1, RF-2, RNF-1, RNF-2, RNF-3, RNF-4  
**Estado:** ✅ Completada

1. Verificar los archivos `main.py` de `servicio-clientes`, `servicio-inventario`, `servicio-envios` y `servicio-pedidos`, agregando `CORSMiddleware` (permitiendo orígenes `*`, métodos `*` y headers `*`) para evitar bloqueos del navegador en peticiones `fetch()`.
2. Crear la carpeta `cliente-web/` con los 4 archivos del frontend:

#### `config.js`
Constantes de configuración centralizadas:
- `API_KEY`: `"changeme-local-key"` (hardcodeada, aceptable para proyecto universitario local).
- `URL_CLIENTES`, `URL_INVENTARIO`, `URL_ENVIOS`, `URL_PEDIDOS` apuntando a `localhost` con sus puertos correspondientes.

#### `styles.css`
Estilos propios minimalistas:
- Variables CSS para paleta de colores (primario, fondo, texto, error, éxito).
- Layout general: sidebar o barra de navegación horizontal con tabs.
- Estilos para: tablas (zebra stripes), formularios, botones (primario, peligro, secundario), mensajes de error/éxito, spinner de carga, panel de detalle/modal.
- El diseño es funcional en pantallas ≥ 1024px de ancho.

#### `index.html`
Esqueleto HTML5 que:
- Carga `config.js`, `styles.css` y `app.js` (en ese orden).
- Define el elemento de navegación con 5 botones/tabs: **Dashboard**, **Clientes**, **Inventario**, **Pedidos**, **Envíos**.
- Define 5 secciones `<section id="...">` correspondientes, inicialmente ocultas (excepto Dashboard).
- No contiene lógica JS inline; toda la lógica va en `app.js`.

#### `app.js` (esqueleto inicial)
- Función `showSection(sectionId)` que muestra la sección activa y oculta las demás, y marca el tab activo con una clase CSS.
- Event listeners en los botones de navegación que llaman a `showSection()`.
- Función utilitaria `apiFetch(url, options)` que envuelve `fetch()` añadiendo automáticamente los headers `X-API-Key` y `Content-Type: application/json`.
- Función utilitaria `showError(sectionId, message)` que muestra un mensaje de error en la sección activa.
- Función utilitaria `showLoading(sectionId, isLoading)` que muestra/oculta el spinner de carga.
- Al cargar la página, mostrar la sección Dashboard.

**Criterio de done:** `index.html` abre en el navegador, muestra los 5 tabs y la navegación entre secciones funciona sin recargar la página. La consola no muestra errores de JS.

---

### T-24 — Dashboard: estado de salud de los 4 servicios

**RF cubiertos:** RF-3, CF-3  
**Estado:** ✅ Completada

En la sección `#dashboard` de `index.html`, agregar tarjetas (cards) para los 4 servicios.

En `app.js`, implementar:
- Función `loadDashboard()` que llama en paralelo (`Promise.allSettled`) a:
  - `GET ${CONFIG.URL_CLIENTES}/health`
  - `GET ${CONFIG.URL_INVENTARIO}/health`
  - `GET ${CONFIG.URL_ENVIOS}/health`
  - `GET ${CONFIG.URL_PEDIDOS}/health`
- Para cada resultado, actualiza la tarjeta del servicio correspondiente con:
  - `✅ Activo` + versión + estado, si responde 200.
  - `❌ Caído` + mensaje de error, si falla o responde error.
- Llama a `loadDashboard()` automáticamente al mostrar la sección Dashboard.
- Botón **Actualizar** en la sección para volver a consultar los 4 servicios.

**Criterio de done:** Con los 4 servicios corriendo, el Dashboard muestra `✅ Activo` para los 4. Al detener un servicio, muestra `❌ Caído` para ese servicio sin afectar los demás.

**🛑 PAUSA al terminar T-23 y T-24 — Verificar navegación SPA y Dashboard en el navegador. Esperar aprobación para Bloque 2.**

---

## Bloque 2 — Secciones Clientes e Inventario

### T-25 — Sección Clientes

**RF cubiertos:** RF-4 (4.1–4.5), CF-4, CF-5  
**Estado:** ✅ Completada

En la sección `#clientes` de `index.html`, agregar:
- Tabla de clientes con columnas: ID, Nombre, Email, Zona, Estado, Acciones.
- Formulario de creación (campos: Nombre completo, Email, Teléfono, Dirección, Zona de cobertura — selector con opciones `LOCAL`, `REGIONAL`, `NACIONAL`) con botón **Crear Cliente**.
- Panel/modal de detalle de cliente (mostrar al hacer clic en el ID).

En `app.js`, implementar:
- `loadClientes()` → `GET /customers` → renderiza tabla; si está vacía muestra "No hay registros disponibles."
- `createCliente(formData)` → `POST /customers` → recarga tabla si éxito; muestra error si falla.
- `getClienteDetail(id)` → `GET /customers/{id}` → muestra panel/modal con datos.
- `deactivateCliente(id)` → `DELETE /customers/{id}` → recarga tabla; muestra error si falla.
- `reactivateCliente(id)` → `PATCH /customers/{id}/reactivate` → recarga tabla; muestra error si falla.
- Botones **Desactivar** (solo para activos) y **Reactivar** (solo para inactivos) en cada fila.

**Criterio de done:** Listar, crear, desactivar y reactivar clientes funciona desde el navegador. Los errores del backend se muestran en español.

---

### T-26 — Sección Inventario

**RF cubiertos:** RF-5 (5.1–5.3), CF-6, CF-7  
**Estado:** ✅ Completada

En la sección `#inventario` de `index.html`, agregar:
- Tabla de productos con columnas: ID, SKU, Nombre, Precio, Stock, Peso (kg), Estado, Acciones.
- Formulario de creación (campos obligatorios: SKU, Nombre, Descripción, Precio, Stock inicial, Peso en kg `weight_kg`) con botón **Crear Producto**.
- Formulario de edición (pre-poblado con datos actuales: SKU, Nombre, Descripción, Precio, Stock disponible, `weight_kg`) con botón **Guardar Cambios**. Se muestra al hacer clic en **Editar** en la fila del producto.

En `app.js`, implementar:
- `loadInventario()` → `GET /products` → renderiza tabla.
- `createProducto(formData)` → `POST /products` → recarga tabla si éxito.
- `loadEditForm(id)` → `GET /products/{id}` → pre-puebla formulario de edición.
- `updateProducto(id, formData)` → `PATCH /products/{id}` → recarga tabla si éxito.

**Criterio de done:** Listar, crear y editar productos funciona desde el navegador.

**🛑 PAUSA al terminar T-25 y T-26 — Verificar secciones Clientes e Inventario en el navegador. Esperar aprobación para Bloque 3.**

---

## Bloque 3 — Sección Pedidos

### T-27 — Sección Pedidos

**RF cubiertos:** RF-6 (6.1–6.4), CF-8, CF-9, CF-10, CF-11  
**Estado:** ✅ Completada

En la sección `#pedidos` de `index.html`, agregar:
- Tabla de pedidos con columnas: ID, Cliente, Zona, Total, Estado, ID Envío, Fecha, Acciones.
- Sub-panel "Nuevo Pedido" (formulario colapsable o integrado) con:
  - Selector `<select>` poblado con clientes activos (`GET /customers`) para evitar ingresar IDs numéricos a mano.
  - Sección dinámica de items: cada fila tiene selector `<select>` poblado con productos disponibles (`GET /products`) y campo `quantity`; botón **+ Agregar producto** para añadir filas; botón **✕** por fila para eliminar.
  - Botón **Crear Pedido** (deshabilitado si no hay items).
- Panel/modal de detalle de pedido.

En `app.js`, implementar:
- `loadPedidos()` → `GET /orders` → renderiza tabla.
- Lógica de items dinámicos: `addItemRow()`, `removeItemRow(rowIndex)`, `getItemsFromForm()`.
- `createPedido()` → construye el body con `customer_id` y `items[]` → `POST /orders` → recarga tabla si 201; muestra error si falla.
- `getPedidoDetail(id)` → `GET /orders/{id}` → muestra panel/modal con items y estado de envío (`shipment_detail` si `shipment_status` es null).
- `cancelPedido(id)` → `confirm()` → `PATCH /orders/{id}/cancel` → recarga tabla; muestra error 409 en español si aplica.
- Columna **Acciones**: botón **Cancelar** solo visible para pedidos en estado `PENDING` o `CONFIRMED`.

**Criterio de done:** Crear pedido con items dinámicos funciona; la tabla lista los pedidos; el detalle muestra items y estado de envío; la cancelación funciona y muestra errores en español.

**🛑 PAUSA al terminar T-27 — Verificar sección Pedidos completa en el navegador. Esperar aprobación para Bloque 4.**

---

## Bloque 4 — Sección Envíos y pulido final

### T-28 — Sección Envíos

**RF cubiertos:** RF-7 (7.1–7.3), CF-12, CF-13  
**Estado:** ⬜ Pendiente

En la sección `#envios` de `index.html`, agregar:
- Tabla de guías con columnas: ID, ID Pedido, Destinatario, Zona, Estado, Fecha, Acciones.
- Panel/modal de detalle de guía.
- Selector de nuevo estado + botón **Confirmar** (en la fila o en el modal de detalle).

En `app.js`, implementar:
- `loadEnvios()` → `GET /shipments` → renderiza tabla.
- `getEnvioDetail(id)` → `GET /shipments/{id}` → muestra panel/modal.
- `changeShipmentStatus(id, currentStatus)` → muestra selector con estados válidos según `currentStatus`:
  - `PENDING` → puede ir a `IN_TRANSIT` o `CANCELLED`.
  - `IN_TRANSIT` → puede ir a `DELIVERED`.
  - `DELIVERED`, `CANCELLED` → botón **Cambiar Estado** ausente o deshabilitado.
- Tras confirmar → `PATCH /shipments/{id}/status` → recarga tabla.

**Criterio de done:** Listar guías, ver detalle y cambiar estado funciona. Guías en estado terminal no tienen botón de cambio de estado activo.

---

### T-29 — Manejo de errores global y feedback visual

**RF cubiertos:** RF-8, CF-14, CF-15  
**Estado:** ⬜ Pendiente

Revisar y completar en `app.js`:
- `apiFetch()` captura errores de red (`catch`) y respuestas de error HTTP: extrae `detail` del JSON si está disponible, o usa mensajes genéricos en español.
- Para `401` → mensaje específico: `"Error de autenticación: verifica la API Key en config.js."`.
- Para errores de red → `"No se pudo conectar con el servicio. Verifica que esté ejecutándose."`.
- `showError(sectionId, message)` muestra el mensaje 5 segundos y luego lo oculta automáticamente.
- `showLoading(sectionId, isLoading)` muestra el spinner antes de cada `fetch()` y lo oculta al terminar (éxito o error).

**Criterio de done:** Todos los errores del backend (400, 401, 404, 409, 422, 502, 503) y de red muestran mensajes legibles en español en la UI. El spinner aparece y desaparece correctamente.

---

### T-30 — Verificación de Criterios de Finalización (CF-1 a CF-16)

**RF cubiertos:** Sección 9 de la spec  
**Estado:** ⬜ Pendiente

Recorrer la lista de CFs en `spec.md` y marcar cada uno:

- [ ] CF-1:  `index.html` carga en el navegador sin errores en la consola.
- [ ] CF-2:  La navegación entre las 5 secciones funciona sin recarga de página.
- [ ] CF-3:  El Dashboard muestra el estado real de los 4 servicios.
- [ ] CF-4:  La tabla de Clientes lista y el formulario de creación agrega uno nuevo.
- [ ] CF-5:  Las acciones Desactivar y Reactivar funcionan y la tabla se actualiza.
- [ ] CF-6:  La tabla de Inventario lista y el formulario de creación agrega un producto.
- [ ] CF-7:  El formulario de edición pre-carga datos y guarda cambios con `PATCH`.
- [ ] CF-8:  El formulario de nuevo pedido permite agregar y eliminar items dinámicamente.
- [ ] CF-9:  `POST /orders` crea un pedido y la tabla se recarga.
- [ ] CF-10: El detalle de pedido muestra items y estado de envío (o "No disponible temporalmente").
- [ ] CF-11: La cancelación de un pedido funciona; errores 409 se muestran en español.
- [ ] CF-12: La tabla de Envíos lista guías; el detalle muestra todos los campos.
- [ ] CF-13: El cambio de estado funciona; guías terminales no muestran botón de cambio.
- [ ] CF-14: Todos los errores HTTP muestran mensajes legibles en español en la UI.
- [ ] CF-15: El indicador de carga se muestra y desaparece correctamente.
- [ ] CF-16: Ninguna URL ni API Key está hardcodeada fuera de `config.js`.

**🛑 PAUSA FINAL — Verificar todos los CFs manualmente en el navegador con los 4 servicios corriendo. Esperar aprobación antes de hacer commit de Fase 5.**

---

## Resumen del plan

| Bloque | Tareas      | Verificación manual                                   | Pausa |
|--------|-------------|-------------------------------------------------------|-------|
| **Bloque 1** | T-23, T-24  | Navegación SPA + Dashboard en navegador          | 🛑 Después de T-24 |
| **Bloque 2** | T-25, T-26  | Clientes e Inventario en navegador               | 🛑 Después de T-26 |
| **Bloque 3** | T-27        | Pedidos completo en navegador                    | 🛑 Después de T-27 |
| **Bloque 4** | T-28, T-29, T-30 | Envíos + pulido + verificación CF completa  | 🛑 Después de T-30 |

**Total de tareas:** 8 (T-23 a T-30) | Sin pruebas `pytest` — verificación 100% manual en navegador.
