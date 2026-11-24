# LogiFlow SOA — Sistema de Gestión de Pedidos y Entregas

Sistema de integración empresarial basado en **Arquitectura Orientada a Servicios (SOA)** con 4 microservicios autónomos desarrollados en **FastAPI** y una interfaz de usuario **Single-Page Application (SPA)** en HTML5, CSS3 y JavaScript ES6+ puro (sin frameworks ni dependencias de Node.js).

---

## 1. Descripción del Sistema

El sistema gestiona de extremo a extremo el ciclo de vida de compras corporativas: catálogo y validación de clientes, control de existencias con reservas atómicas, cotización zonal y seguimiento de guías de entrega, y orquestación distribuida de pedidos con tolerancia a fallos.

### Principios de Arquitectura SOA
1. **Autonomía e Independencia:** Cada microservicio es un proceso independiente; no existen dependencias de código cruzadas ni imports entre servicios.
2. **Aislamiento Estricto de Datos:** Cada microservicio posee y gestiona exclusivamente su propia base de datos SQLite (`clientes.db`, `inventario.db`, `envios.db`, `pedidos.db`). Ningún servicio accede directamente a la base de datos de otro.
3. **Comunicación Exclusivamente HTTP REST:** La interacción inter-servicios se realiza mediante clientes HTTP asíncronos (`httpx`).
4. **Patrón Saga (Compensación):** `servicio-pedidos` actúa como orquestador del flujo transaccional distribuido. Si la cotización, persistencia o creación del despacho falla tras haber reservado inventario, se ejecuta automáticamente un rollback (compensación) liberando las existencias.
5. **Seguridad Unificada:** Todos los endpoints de negocio exigen el header `X-API-Key`. Los endpoints `/health` son públicos para monitoreo y verificación de salud.
6. **CORS Habilitado:** Todos los servicios FastAPI implementan `CORSMiddleware` para permitir la comunicación directa con el frontend local.

---

## 2. Mapa de Microservicios y Puertos

| Servicio | Puerto | Base de Datos | Rol en la Arquitectura | Swagger / OpenAPI |
|---|---|---|---|---|
| **servicio-clientes** | `8001` | `clientes.db` | Catálogo de clientes, direcciones y validación de estado activo. | [http://localhost:8001/docs](http://localhost:8001/docs) |
| **servicio-inventario** | `8002` | `inventario.db` | Catálogo de productos, existencias, reservas atómicas y liberación de stock. | [http://localhost:8002/docs](http://localhost:8002/docs) |
| **servicio-envios** | `8003` | `envios.db` | Tarifas por zona (`LOCAL`, `REGIONAL`, `NACIONAL`) y ciclo de vida de guías. | [http://localhost:8003/docs](http://localhost:8003/docs) |
| **servicio-pedidos** | `8004` | `pedidos.db` | Orquestador Saga central: validación, reserva, cotización, persistencia y despacho. | [http://localhost:8004/docs](http://localhost:8004/docs) |
| **cliente-web** | `5500` | — | Frontend SPA: Dashboard en tiempo real, gestión de catálogo, pedidos y rastreo. | [http://localhost:5500](http://localhost:5500) |

---

## 3. Estructura del Proyecto

```text
proyecto-soa-pedidos/
├── cliente-web/                  # Frontend SPA puro (HTML/CSS/JS)
│   ├── index.html                # Estructura principal y navegación por pestañas
│   ├── styles.css                # Estilos visuales estilo e-commerce moderno
│   ├── config.js                 # URLs de los servicios y API Key del frontend
│   └── app.js                    # Lógica interactiva, llamadas fetch() y modales
├── docs/                         # Documentación de arquitectura
│   └── constitution.md           # Principios innegociables del proyecto
├── servicio-clientes/            # Microservicio de Clientes (:8001)
│   ├── auth.py                   # Verificación de X-API-Key
│   ├── config.py                 # Carga de variables de entorno
│   ├── database.py               # Conexión SQLite y función init_db()
│   ├── main.py                   # API FastAPI y rutas de clientes
│   ├── models.py                 # Modelo relacional Customer
│   ├── schemas.py                # Esquemas Pydantic
│   ├── pytest.ini                # Configuración de pruebas
│   └── tests/                    # 90 pruebas unitarias y de integración
├── servicio-inventario/          # Microservicio de Catálogo e Inventario (:8002)
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── main.py                   # Rutas de productos, reserve y release
│   ├── schemas.py
│   ├── pytest.ini
│   └── tests/                    # 79 pruebas unitarias y de integración
├── servicio-envios/              # Microservicio de Envíos (:8003)
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── main.py                   # Rutas de cotización, guías y transiciones
│   ├── schemas.py
│   ├── pytest.ini
│   └── tests/                    # 58 pruebas unitarias y de integración
├── servicio-pedidos/             # Microservicio Orquestador de Pedidos (:8004)
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── clients.py                # Clientes HTTP httpx hacia los 3 microservicios
│   ├── main.py                   # Endpoints POST /orders (Saga), GET, PATCH /cancel
│   ├── schemas.py
│   ├── pytest.ini
│   └── tests/                    # 74 pruebas unitarias y de orquestación
├── specs/                        # Especificaciones funcionales SDD por fase
│   ├── 001-servicio-clientes/
│   ├── 002-servicio-inventario/
│   ├── 003-servicio-envios/
│   ├── 004-orquestador-pedidos/
│   └── 005-cliente-web/
├── .env.example                  # Plantilla de variables de entorno
├── AGENTS.md                     # Reglas de desarrollo y convenciones
├── MEMORY.md                     # Bitácora de estado técnico del proyecto
├── requirements.txt              # Dependencias de Python del proyecto
└── run_services.py               # Script para iniciar todos los servicios simultáneamente
```

---

## 4. Instalación de Dependencias

### Prerrequisitos
- **Python 3.11** o superior instalado en el sistema.
- Navegador web moderno (Chrome, Firefox, Edge, Safari).

### Paso 1: Clonar o abrir el repositorio
Navega a la carpeta raíz del proyecto en tu terminal:
```bash
cd "proyecto-soa-pedidos"
```

### Paso 2: Crear y activar entorno virtual
En **Windows (PowerShell)**:
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

En **Linux / macOS**:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Paso 3: Instalar dependencias
Instala los paquetes necesarios definidos en `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## 5. Configuración del Entorno

### Configuración de `.env` (Backend)
Crea tu archivo `.env` local en la raíz del proyecto copiando la plantilla `.env.example`:

En **Windows (PowerShell)**:
```powershell
Copy-Item .env.example .env
```

En **Linux / macOS**:
```bash
cp .env.example .env
```

Contenido representativo de `.env`:
```ini
# Puertos de escucha de cada servicio
PORT_CLIENTES=8001
PORT_INVENTARIO=8002
PORT_ENVIOS=8003
PORT_PEDIDOS=8004

# URLs base (consumidas por el orquestador y el frontend)
URL_CLIENTES=http://localhost:8001
URL_INVENTARIO=http://localhost:8002
URL_ENVIOS=http://localhost:8003
URL_PEDIDOS=http://localhost:8004

# Clave de seguridad (X-API-Key)
API_KEY=changeme-local-key

# Bases de datos SQLite independientes
DB_CLIENTES=clientes.db
DB_INVENTARIO=inventario.db
DB_ENVIOS=envios.db
DB_PEDIDOS=pedidos.db

# Tarifas fijas de envío
RATE_LOCAL=50
RATE_REGIONAL=100
RATE_NACIONAL=200

# Configuración operativa
DEBUG=true
LOG_LEVEL=info
HTTP_TIMEOUT_SECONDS=10
```

> [!WARNING]
> Nunca guardes contraseñas ni claves de producción en el repositorio de control de versiones. El archivo `.env` está expresamente excluido mediante `.gitignore`.

### Configuración de `cliente-web/config.js` (Frontend)
El cliente web dispone de su propio archivo de configuración en `cliente-web/config.js`. Asegúrate de que `API_KEY` coincida con la configurada en tu `.env`:

```javascript
// cliente-web/config.js
const CONFIG = {
  API_KEY: "changeme-local-key",
  URL_CLIENTES: "http://localhost:8001",
  URL_INVENTARIO: "http://localhost:8002",
  URL_ENVIOS: "http://localhost:8003",
  URL_PEDIDOS: "http://localhost:8004"
};
```

---

## 6. Cómo Arrancar Todo el Sistema

El proyecto incluye un script orquestador (`run_services.py`) que levanta en paralelo los 4 microservicios FastAPI con Uvicorn y sirve el cliente web con el servidor HTTP nativo de Python:

```bash
python run_services.py
```

### Salida esperada en consola:
```text
Iniciando servicios de LogiFlow SOA...

Todos los servicios estan corriendo:
  - Cliente Web:         http://localhost:5500
  - Servicio Clientes:   http://localhost:8001/docs
  - Servicio Inventario: http://localhost:8002/docs
  - Servicio Envios:     http://localhost:8003/docs
  - Servicio Pedidos:    http://localhost:8004/docs

Presiona Ctrl+C para detener todos los servicios.
```

Abre tu navegador en **[http://localhost:5500](http://localhost:5500)** para acceder a la aplicación web.

Para detener todos los servicios de forma limpia, presiona **`Ctrl + C`** en la terminal.

---

## 7. Cómo Ejecutar las Pruebas Automatizadas (`pytest`)

El proyecto cuenta con **301 pruebas automatizadas** que cubren autenticación, validación de esquemas, operaciones atómicas en SQLite, resiliencia ante fallos de red (`httpx`) y compensación Saga.

Debido a que cada microservicio es una unidad autónoma con su propio `pytest.ini` aislado, las pruebas se ejecutan especificando la configuración de cada servicio:

### Ejecutar por servicio:

**1. Servicio Clientes (90 pruebas):**
```bash
pytest -c servicio-clientes/pytest.ini servicio-clientes/tests -q
```

**2. Servicio Inventario (79 pruebas):**
```bash
pytest -c servicio-inventario/pytest.ini servicio-inventario/tests -q
```

**3. Servicio Envíos (58 pruebas):**
```bash
pytest -c servicio-envios/pytest.ini servicio-envios/tests -q
```

**4. Servicio Pedidos (74 pruebas):**
```bash
pytest -c servicio-pedidos/pytest.ini servicio-pedidos/tests -q
```

### Ejecutar todas las pruebas en un solo comando:

En **Windows (PowerShell)**:
```powershell
pytest -c servicio-clientes/pytest.ini servicio-clientes/tests -q; `
pytest -c servicio-inventario/pytest.ini servicio-inventario/tests -q; `
pytest -c servicio-envios/pytest.ini servicio-envios/tests -q; `
pytest -c servicio-pedidos/pytest.ini servicio-pedidos/tests -q
```

En **Linux / macOS (Bash)**:
```bash
pytest -c servicio-clientes/pytest.ini servicio-clientes/tests -q && \
pytest -c servicio-inventario/pytest.ini servicio-inventario/tests -q && \
pytest -c servicio-envios/pytest.ini servicio-envios/tests -q && \
pytest -c servicio-pedidos/pytest.ini servicio-pedidos/tests -q
```

---

## 8. Funcionalidades del Cliente Web

- **Dashboard:** Monitor de conectividad que consulta en paralelo el endpoint `/health` de los 4 servicios y reporta estado (`Activo` / `Caído`), versión y latencia en milisegundos.
- **Clientes:** Registro con validación de zonas de cobertura, detalle en modal, y desactivación/reactivación lógica (`is_active`).
- **Inventario:** Alta de productos con SKU, precio, existencias y peso en kg para cálculo de envío; edición en modal pre-poblado.
- **Pedidos:**
  - Selectores dinámicos alimentados por los microservicios (sin ingreso manual de IDs).
  - Manejo dinámico de líneas de pedido con validación de duplicados y existencias.
  - Orquestación Saga con feedback visual en tiempo real.
  - Consulta detallada con soporte para modo degradado si el servicio de despachos no responde.
  - Cancelación de pedidos activos con reversión automática de stock y cancelación de guía.
- **Envíos:** Visualización de guías generadas y cambio controlado de estados (`PENDING` → `IN_TRANSIT` → `DELIVERED` o `CANCELLED`) respetando la máquina de estados del backend.
