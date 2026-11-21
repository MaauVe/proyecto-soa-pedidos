# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 1 — servicio-clientes, implementación en curso
- **Tarea completada**: T-03 ✅ — Autenticación X-API-Key (19/19 pytest, suite 28/28, 2026-11-21)
- **Siguiente tarea**: T-04 — POST /customers — pendiente de aprobación
- **Fecha de inicio**: 2026-11-19

## Decisión de Testing (CRÍTICA — aplicar en T-04 a T-11)
El sandbox bloquea todo event loop async (asyncio, anyio) y conexiones TCP.
- Handlers y dependencias FastAPI → declarar como `def` síncronos, no `async def`
- Tests → llamar funciones directamente sin `asyncio.run` ni `TestClient`
- Para lógica de endpoints: extraer y probar la función de servicio directamente

## Decisiones Técnicas Acumuladas
| Decisión | Valor |
|---|---|
| `.env` / `requirements.txt` | Compartidos en raíz; `find_dotenv()` en `config.py` |
| `clientes.db` | En `servicio-clientes/` vía `Path(__file__).parent` |
| Test client HTTP | Bloqueado en sandbox; usar inspección directa de handlers |
| SQLAlchemy | v2.1.9 síncrono; `SessionLocal` en `database.py` |
| httpx2 | Instalado (Starlette 1.10 lo requiere); no usable en sandbox |

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
2. 🔵 T-04: POST /customers — crear cliente con validación de correo único.
3. ⬜ T-05 a T-11: Endpoints restantes de servicio-clientes.
4. ⬜ Fases 2-4: Implementar servicios inventario, envíos, pedidos.
5. ⬜ Fase 5: Implementar cliente-web.
