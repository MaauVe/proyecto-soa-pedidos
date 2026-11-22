# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 4 — servicio-pedidos 🔄 EN PROGRESO (Bloque 2 completado: 53/53 tests ✅)
- **Última tarea**: T-17 y T-18 ✅ — clients.py (httpx) y POST /orders con Saga de compensación
- **Siguiente paso**: Bloque 3 — T-19 (GET /orders/{id}), T-20 (GET /orders), T-21 (cancel) y T-22 (cierre)
- **Fecha inicio Fase 4**: 2026-11-22

## Decisiones Técnicas Consolidadas — servicio-envios
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo en `servicio-envios/envios.db` (sin ORM externo) |
| Configuración | `.env` raíz con `find_dotenv()`, puerto 8003 |
| Tarifas de zonas | Planas desde `.env`: `RATE_LOCAL=50`, `RATE_REGIONAL=100`, `RATE_NACIONAL=200` |
| Endpoints listos | `GET /health`, `GET /zones`, `POST /quote`, `POST /shipments`, `GET /shipments/{id}`, `GET /shipments`, `PATCH /shipments/{id}/status` |
| Máquina de estados | `PENDING → IN_TRANSIT → DELIVERED` / `CANCELLED`; terminales rechazan cambios con 409 |
| Autenticación | `X-API-Key` obligatoria (salvo `GET /health`), 401 si ausente/inválida |
| Pruebas consolidadas | 2 archivos: `test_base_auth.py` (29) y `test_shipments.py` (29) = 58 tests |

## Decisiones Arquitectónicas
- 4 servicios FastAPI independientes, bajo acoplamiento SOA.
- SQLite aislado por servicio; comunicación exclusivamente HTTP REST con `httpx`.
- Variables de entorno centralizadas sin credenciales en Git.

## Decisiones Técnicas — servicio-pedidos
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo (sin ORM), `pedidos.db` en `servicio-pedidos/` |
| Tablas | `orders` (11 cols) + `order_items` (7 cols) |
| Estados de pedido | `PENDING → CONFIRMED`; terminales: `CANCELLED`, `FAILED` |
| Cancelación | Solo si envío en `PENDING`; IN_TRANSIT/DELIVERED → 409 |
| Saga fallida | Pedido queda `FAILED` + `compensation_error`; intervención manual |
| Fallo envíos en GET | 200 degradado: `shipment_status: null` + `shipment_detail` |
| Semilla | Sin seed; `pedidos.db` arranca vacía; mocks en pytest |
| Timeout HTTP | `HTTP_TIMEOUT_SECONDS` desde `.env` (default 10 s) |

## Próximos Pasos
1. ⬜ T-19: `GET /orders/{id}` — detalle con estado degradado de envío
2. ⬜ T-20: `GET /orders` — listado paginado con filtros
3. ⬜ T-21: `PATCH /orders/{id}/cancel` — cancelación con Saga
4. ⬜ T-22: Revisión final y criterios CF-1 a CF-17
5. ⬜ Fase 5: `cliente-web`
