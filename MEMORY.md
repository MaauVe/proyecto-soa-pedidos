# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 2 — servicio-inventario ✅ COMPLETADA Y VERIFICADA (79/79 tests)
- **Última tarea**: T-14 ✅ — Criterios de finalización CF-1 a CF-12 cumplidos
- **Siguiente paso**: Fase 3 — Servicio de Envíos (puerto 8003, envios.db)
- **Fecha de cierre Fase 2**: 2026-11-21

## Decisiones Técnicas Consolidadas — servicio-inventario
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo en `servicio-inventario/inventario.db` (sin ORM externo) |
| Configuración | `.env` raíz cargado con `find_dotenv()`, puerto 8002 |
| Handlers y Auth | Funciones síncronas `def`, `X-API-Key` obligatoria (salvo `/health`) |
| Seed | 5 productos semilla automáticos (1 inactivo con stock 0) |
| CRUD productos | Validación SKU insensible a mayúsculas, soft-delete y reactivación |
| Operaciones stock | Transacciones atómicas SQLite (rollback total en reserva, release suma siempre) |
| Pruebas consolidadas | 3 archivos: `test_base_auth.py`, `test_products_crud.py`, `test_stock_ops.py` |

## Decisiones Arquitectónicas
- 4 servicios FastAPI independientes, bajo acoplamiento SOA.
- SQLite aislado por servicio; comunicación exclusivamente HTTP REST con `httpx`.
- Variables de entorno centralizadas sin credenciales en Git.

## Próximos Pasos
1. ⬜ Commit en GitHub de Fase 2 completada (responsabilidad del desarrollador).
2. 🔵 Fase 3: Redacción y aprobación de `specs/003-servicio-envios/spec.md`.
3. ⬜ Fase 3: Plan `tasks.md` e implementación TDD de `servicio-envios` (puerto 8003).
4. ⬜ Fase 4: Spec + implementación de `servicio-pedidos` (orquestador, puerto 8004).
5. ⬜ Fase 5: Implementación de `cliente-web`.
