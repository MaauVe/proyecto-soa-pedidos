# Servicio Orquestador de Pedidos — Puerto 8004

Microservicio FastAPI que orquesta el flujo de negocio completo de pedidos y entregas en el sistema SOA.

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
| `API_KEY` | Clave requerida en header `X-API-Key` | `changeme-local-key` |
| `PORT_PEDIDOS` | Puerto donde escucha el servicio | `8004` |
| `DB_PEDIDOS` | Archivo SQLite en `servicio-pedidos/` | `pedidos.db` |
| `URL_CLIENTES` | URL base de servicio-clientes | `http://localhost:8001` |
| `URL_INVENTARIO` | URL base de servicio-inventario | `http://localhost:8002` |
| `URL_ENVIOS` | URL base de servicio-envios | `http://localhost:8003` |
| `HTTP_TIMEOUT_SECONDS` | Timeout de llamadas HTTP externas | `10` |
| `LOG_LEVEL` | Nivel de logging (`debug`, `info`, `warning`) | `info` |

## Arranque del servicio

Desde la carpeta `servicio-pedidos/`:

```bash
cd servicio-pedidos
uvicorn main:app --host 0.0.0.0 --port 8004 --reload
```

## Documentación interactiva

Una vez en ejecución:
- **Swagger UI:** http://localhost:8004/docs
- **ReDoc:** http://localhost:8004/redoc
- **Health check:** http://localhost:8004/health

## Ejecución de pruebas

Desde la carpeta raíz del proyecto:

```bash
pytest -c servicio-pedidos/pytest.ini servicio-pedidos/tests -v
```
