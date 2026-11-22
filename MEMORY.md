# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 3 — servicio-envios (puerto 8003, envios.db)
- **Última tarea**: T-04 ✅ — Bloque 1 completado y verificado (20/20 tests en verde)
- **Siguiente paso**: Bloque 2 — Zonas, cotización y CRUD de envíos (T-05 a T-10)
- **Fecha**: 2026-11-22

## Decisiones Técnicas Consolidadas — servicio-envios
| Decisión | Valor |
|---|---|
| Base de datos | SQLite nativo en `servicio-envios/envios.db` (sin ORM externo) |
| Configuración | `.env` raíz con `find_dotenv()`, puerto 8003 |
| Tarifas de zonas | Planas desde `.env`: `RATE_LOCAL=50`, `RATE_REGIONAL=100`, `RATE_NACIONAL=200` |
| Estados de envío | `PENDING → IN_TRANSIT → DELIVERED` / `CANCELLED` |
| Autenticación | `X-API-Key` obligatoria (salvo `GET /health`), 401 si ausente/inválida |
| Pruebas consolidadas | 2 archivos: `test_base_auth.py` y `test_shipments.py` |

## Decisiones Arquitectónicas
- 4 servicios FastAPI independientes, bajo acoplamiento SOA.
- SQLite aislado por servicio; comunicación exclusivamente HTTP REST con `httpx`.
- Variables de entorno centralizadas sin credenciales en Git.

## Próximos Pasos
1. ⬜ Usuario: actualizar `.env` local y commit de Bloque 1 en GitHub.
2. ⬜ Fase 3: Bloque 2 — Implementación de `GET /zones`, `POST /quote` y creación/consulta de envíos.
3. ⬜ Fase 3: Bloque 3 — Máquina de estados y verificación final de CFs.
4. ⬜ Fase 4: Spec + implementación de `servicio-pedidos` (orquestador, puerto 8004).
5. ⬜ Fase 5: Implementación de `cliente-web`.
