# Servicio de Clientes — Puerto 8001

Microservicio FastAPI para la gestión del catálogo de clientes del sistema SOA.

## Requisitos previos

- Python 3.11+
- Dependencias instaladas desde la raíz del proyecto:
  ```bash
  pip install -r requirements.txt
  ```
- Archivo `.env` configurado en la raíz del proyecto (copiar desde `.env.example`).

## Variables de entorno relevantes (en `.env` raíz)

| Variable | Descripción | Valor de ejemplo |
|---|---|---|
| `API_KEY` | Clave de autenticación para los endpoints protegidos | `changeme-local-key` |
| `PORT_CLIENTES` | Puerto donde escucha el servicio | `8001` |
| `DB_CLIENTES` | Nombre del archivo SQLite (se crea en `servicio-clientes/`) | `clientes.db` |
| `LOG_LEVEL` | Nivel de logging (`debug`, `info`, `warning`) | `info` |

## Arranque del servicio

Desde la carpeta `servicio-clientes/`:

```bash
cd servicio-clientes
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

O desde la raíz del proyecto:

```bash
uvicorn servicio-clientes.main:app --host 0.0.0.0 --port 8001 --reload
```

## Documentación interactiva

Una vez en ejecución:
- **Swagger UI:** http://localhost:8001/docs
- **ReDoc:** http://localhost:8001/redoc
- **Health check:** http://localhost:8001/health

## Ejecución de pruebas

Desde la carpeta `servicio-clientes/`:

```bash
cd servicio-clientes
pytest tests/ -v
```

## Base de datos

El archivo `clientes.db` se crea automáticamente dentro de `servicio-clientes/`
al arrancar el servicio por primera vez. Si la tabla está vacía, se cargan
entre 3 y 5 clientes de prueba como datos semilla.

> **Nota:** `clientes.db` está excluido de Git por `.gitignore`.
