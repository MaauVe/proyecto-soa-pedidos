# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 2 — servicio-inventario 🔵 EN PROGRESO (Bloque 1 completado: 22/22 tests)
- **Última acción**: T-01 a T-04 completadas ✅ (Base, SQLite DDL, Seed 5 items, Auth y /health)
- **Siguiente tarea**: T-05 — `POST /products` (CRUD completo T-05 a T-10)
- **Fecha inicio Fase 2**: 2026-11-21

## Decisiones Técnicas Consolidadas — servicio-inventario
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo en `servicio-inventario/inventario.db` (sin ORM externo) |
| Configuración | `.env` raíz cargado con `find_dotenv()`, puerto 8002 |
| Handlers y Auth | Funciones síncronas `def`, `X-API-Key` obligatoria (salvo `/health`) |
| Seed | 5 productos semilla automáticos (1 inactivo con stock 0) |
| Pruebas consolidadas | 3 archivos: `test_base_auth.py`, `test_products_crud.py`, `test_stock_ops.py` |

## Decisiones de Negocio — servicio-inventario
| Decisión | Valor |
|---|---|
| Reserva fallida | Rollback total (HTTP 409, ningún stock modificado) |
| Validaciones | `unit_price > 0`, `weight_kg > 0`, `stock >= 0`, sin `product_id` duplicados (422) |
| Respuestas stock | Incluyen `name`, `unit_price`, `weight_kg` en 200 OK |
| Desactivar con stock | Permitido; orquestador es responsable |
| Release de inactivo | Siempre restaura stock (HTTP 200) |

## Decisiones Arquitectónicas
- 4 servicios FastAPI independientes, bajo acoplamiento SOA.
- SQLite aislado por servicio; comunicación exclusivamente HTTP REST con `httpx`.
- Variables de entorno centralizadas sin credenciales en Git.

## Próximos Pasos
1. ⬜ Bloque 2: CRUD de productos (`T-05` a `T-10` en `tests/test_products_crud.py`).
2. ⬜ Bloque 3: Operaciones de stock (`T-11` a `T-13` en `tests/test_stock_ops.py`).
3. ⬜ T-14: Integración final y verificación de criterios CF-1 a CF-12.
4. ⬜ Commit en GitHub de Fase 2 completada (responsabilidad del desarrollador).
