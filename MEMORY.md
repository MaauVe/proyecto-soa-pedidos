# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 1 — servicio-clientes, implementación en curso
- **Tarea completada**: T-02 — Modelo de datos y BD ✅ (9/9 pytest, 2026-11-20)
- **Siguiente tarea**: T-03 — Autenticación X-API-Key + /health — pendiente de aprobación
- **Fecha de inicio**: 2026-11-19

## Decisiones Técnicas T-01
| Decisión | Valor |
|---|---|
| `requirements.txt` / `.env` | Compartidos en raíz; NO duplicar por servicio |
| Carga de `.env` | `find_dotenv()` desde `config.py` (sube por árbol de dirs) |
| `clientes.db` | Vive en `servicio-clientes/` (ruta absoluta via `Path(__file__).parent`) |
| Test client | `httpx2.ASGITransport` (Starlette 1.10 requiere `httpx2`, no `httpx`) |
| `sqlalchemy` | Instalado en venv (v2.1.9); disponible para T-02 |

## Decisiones Arquitectónicas (y por qué)
| Decisión | Justificación |
|---|---|
| 4 servicios FastAPI independientes | Bajo acoplamiento, despliegue autónomo, escenario SOA real |
| SQLite aislado por servicio | Sin dependencias de BD compartida; simplicidad para entorno local académico |
| Ejecución local sin Docker | Reduce complejidad de entorno; foco en lógica SOA, no en infraestructura |
| Comunicación HTTP con `httpx` | Protocolo estándar REST; httpx soporta async y timeouts nativos |
| Seguridad con `X-API-Key` | Mecanismo simple y verificable; evita exponer endpoints sin protección |
| Variables de entorno con `python-dotenv` | Ninguna credencial en código; `.env` excluido de Git |
| Frontend HTML/CSS/JS puro | Sin frameworks; máxima portabilidad y foco en integración de servicios |
| Pydantic para validación | Validación automática de entrada/salida; errores claros y predecibles |

## Aprendizajes y Errores a Evitar
- No compartir modelos Pydantic entre servicios (rompe la independencia).
- No olvidar capturar `httpx.TimeoutException` y `httpx.HTTPStatusError` en el orquestador.
- No hardcodear `localhost:800X`; siempre leer desde variables de entorno.
- Correr `pytest` antes de marcar cualquier tarea como completada.

## Decisiones de Spec — servicio-clientes (aprobada 2026-11-20)
| Decisión | Valor |
|---|---|
| Eliminación | Borrado lógico (`is_active=false`); reactivación por admin |
| Validaciones | Flexible: correo con `@`, teléfono texto libre, zona sin enum |
| Seed | Auto-seed 3–5 clientes al arranque si BD vacía |
| Endpoint validación | 200 activo / 404 no existe / 409 inactivo |

## Próximos Pasos
1. ⬜ Revisión y primer commit en GitHub (responsabilidad del desarrollador).
2. ✅ Fase 1 (Spec): `specs/001-servicio-clientes/spec.md` aprobada + `tasks.md` creado.
3. 🔵 Fase 1 (Impl): T-01 — Estructura base de `servicio-clientes` (siguiente).
4. ⬜ Fases 2-4: Implementar servicios de inventario, envíos y pedidos.
5. ⬜ Fase 5: Implementar `cliente-web`.
