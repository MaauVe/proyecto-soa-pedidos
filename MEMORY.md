# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 1 — servicio-clientes ✅ COMPLETADA Y VERIFICADA (90/90 tests)
- **Última tarea**: T-11 ✅ — Criterios de finalización CF-1 a CF-10 cumplidos
- **Siguiente paso**: Fase 2 — Servicio de Inventario (puerto 8002, inventario.db)
- **Fecha de cierre Fase 1**: 2026-11-21

## Decisiones Técnicas Consolidadas (Fase 1)
| Decisión | Valor |
|---|---|
| Handlers y dependencias | `def` síncronos para evitar bloqueo async en sandbox |
| Tests | Llamadas directas y validación de schemas (sin TestClient) |
| BD clientes | SQLite en `servicio-clientes/clientes.db`, aislada |
| Autenticación | Header `X-API-Key` validado contra `.env` raíz |
| Endpoints completados | `/health`, `POST`, `GET /id`, `GET list`, `PATCH`, `DELETE`, `reactivate`, `validate` |

## Decisiones de Spec — servicio-clientes (2026-11-20)
| Eliminación | Borrado lógico `is_active=false`; reactivación por admin |
| Validaciones | Flexible: correo con `@`, teléfono texto libre, zona libre |
| Seed | Auto-seed 5 clientes al arranque si BD vacía |
| Endpoint validación | 200 activo / 404 no existe / 409 inactivo |

## Decisiones Arquitectónicas
| Decisión | Justificación |
|---|---|
| 4 servicios FastAPI independientes | Bajo acoplamiento, escenario SOA real |
| SQLite aislado por servicio | Sin BD compartida; simplicidad académica |
| Comunicación HTTP con `httpx` | REST estándar; async + timeouts |
| Seguridad con `X-API-Key` | Simple y verificable |
| Variables de entorno con `python-dotenv` | Sin credenciales en código |

## Aprendizajes
- No compartir modelos Pydantic entre servicios (rompe independencia).
- No hardcodear `localhost:800X`; leer desde variables de entorno.
- Correr `pytest tests/ -v` antes de marcar cualquier tarea como completada.

## Próximos Pasos
1. ⬜ Commit en GitHub de la Fase 1 completa (responsabilidad del desarrollador).
2. 🔵 Fase 2: Redacción y aprobación de `specs/002-servicio-inventario/spec.md`.
3. ⬜ Fase 2: Plan `tasks.md` e implementación TDD de `servicio-inventario`.
4. ⬜ Fases 3-4: Implementar servicios envíos y pedidos.
5. ⬜ Fase 5: Implementar cliente-web.
