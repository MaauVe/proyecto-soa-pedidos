# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 1 — servicio-clientes, implementación en curso
- **Tarea completada**: T-10 ✅ — GET /validate (7/7 tests, suite 90/90, 2026-11-21)
- **Siguiente tarea**: T-11 — Revisión final y cierre Fase 1 — pendiente de aprobación
- **Fecha de inicio**: 2026-11-19

## Decisión de Testing (CRÍTICA — aplicar en T-11)
El sandbox bloquea todo event loop async (asyncio, anyio) y conexiones TCP.
- Handlers y dependencias FastAPI → declarar como `def` síncronos, no `async def`
- Tests → llamar funciones directamente sin `asyncio.run` ni `TestClient`
- Para lógica de endpoints: probar directamente la función handler/servicio

## Decisiones Técnicas Acumuladas
| Decisión | Valor |
|---|---|
| `.env` / `requirements.txt` | Compartidos en raíz; `find_dotenv()` en `config.py` |
| `clientes.db` | En `servicio-clientes/` vía `Path(__file__).parent` |
| Test client HTTP | Bloqueado en sandbox; usar llamadas directas y schemas |
| SQLAlchemy | v2.1.9 síncrono; `SessionLocal` en `database.py` |
| Endpoints completados | `/health`, `POST`, `GET /id`, `GET list`, `PATCH`, `DELETE`, `reactivate`, `validate` |

## Decisiones de Spec — servicio-clientes (aprobada 2026-11-20)
| Eliminación | Borrado lógico `is_active=false`; reactivación por admin |
| Validaciones | Flexible: correo con `@`, teléfono texto libre, zona libre |
| Seed | Auto-seed 3–5 clientes al arranque si BD vacía |
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
- No compartir modelos Pydantic entre servicios.
- No hardcodear `localhost:800X`; leer desde variables de entorno.
- Correr `pytest tests/ -v` antes de marcar cualquier tarea como completada.

## Próximos Pasos
1. ⬜ Commit en GitHub tras cada tarea (responsabilidad del desarrollador).
2. 🔵 T-11: Revisión final, casos límite y criterios de finalización Fase 1.
3. ⬜ Fase 2: Servicio de Inventario (spec y tareas).
4. ⬜ Fases 3-4: Implementar servicios envíos, pedidos.
5. ⬜ Fase 5: Implementar cliente-web.
