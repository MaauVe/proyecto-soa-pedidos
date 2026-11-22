# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 3 — servicio-envios ✅ COMPLETADA Y VERIFICADA (58/58 tests)
- **Última tarea**: T-13 ✅ — Criterios de finalización CF-1 a CF-12 cumplidos
- **Siguiente paso**: Fase 4 — Servicio de Pedidos (orquestador, puerto 8004, pedidos.db)
- **Fecha de cierre Fase 3**: 2026-11-22

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

## Próximos Pasos
1. ⬜ Usuario: commit en GitHub de Fase 3 completada.
2. ⬜ Fase 4: Redacción y aprobación de `specs/004-servicio-pedidos/spec.md`.
3. ⬜ Fase 4: Plan `tasks.md` e implementación TDD de `servicio-pedidos` (puerto 8004).
4. ⬜ Fase 5: Implementación de `cliente-web`.
