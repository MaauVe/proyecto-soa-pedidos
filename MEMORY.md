# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 0 — Harness Engineering + Constitución SDD ✅ COMPLETADA
- **Último commit**: pendiente (esperando revisión y primer commit del desarrollador)
- **Fecha de inicio**: 2026-11-19

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

## Próximos Pasos
1. ⬜ Revisión y primer commit en GitHub (responsabilidad del desarrollador).
2. ⬜ Fase 1: Crear `specs/001-servicio-clientes.md` y `tasks.md`.
3. ⬜ Fase 2: Implementar `servicio-clientes` (TDD con pytest).
4. ⬜ Fases 3-5: Implementar servicios de inventario, envíos y pedidos.
5. ⬜ Fase 6: Implementar `cliente-web`.
