# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 3 — servicio-envios (puerto 8003, envios.db)
- **Última tarea**: T-10 ✅ — Bloque 2 completado y verificado (46/46 tests en verde)
- **Siguiente paso**: Bloque 3 — Máquina de estados y verificación final de CFs (T-11 a T-13)
- **Fecha**: 2026-11-22

## Decisiones Técnicas Consolidadas — servicio-envios
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo en `servicio-envios/envios.db` (sin ORM externo) |
| Configuración | `.env` raíz con `find_dotenv()`, puerto 8003 |
| Tarifas de zonas | Planas desde `.env`: `RATE_LOCAL=50`, `RATE_REGIONAL=100`, `RATE_NACIONAL=200` |
| Endpoints listos | `GET /health`, `GET /zones`, `POST /quote`, `POST /shipments`, `GET /shipments/{id}`, `GET /shipments` |
| Estados de envío | `PENDING → IN_TRANSIT → DELIVERED` / `CANCELLED` |
| Autenticación | `X-API-Key` obligatoria (salvo `GET /health`), 401 si ausente/inválida |
| Pruebas consolidadas | 2 archivos: `test_base_auth.py` (29) y `test_shipments.py` (17) |

## Decisiones Arquitectónicas
- 4 servicios FastAPI independientes, bajo acoplamiento SOA.
- SQLite aislado por servicio; comunicación exclusivamente HTTP REST con `httpx`.
- Variables de entorno centralizadas sin credenciales en Git.

## Próximos Pasos
1. ⬜ Usuario: revisión y commit de Bloque 2 en GitHub.
2. ⬜ Fase 3: Bloque 3 — `PATCH /shipments/{id}/status`, máquina de estados y verificación de CF-1 a CF-12.
3. ⬜ Fase 4: Spec + implementación de `servicio-pedidos` (orquestador, puerto 8004).
4. ⬜ Fase 5: Implementación de `cliente-web`.
