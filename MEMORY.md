# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 5 — cliente-web (En progreso: Bloque 1 completado)
- **Última tarea**: T-24 ✅ — Estructura base SPA y Dashboard de salud de microservicios
- **Siguiente paso**: Bloque 2 — T-25 (Clientes) y T-26 (Inventario)
- **Fecha**: 2026-11-22

## Decisiones Técnicas — cliente-web
| Decisión | Valor |
|---|---|
| Arquitectura | Single-Page Application (SPA) pura (HTML5, CSS3, ES6+) |
| Dependencias | Cero frameworks, sin npm, sin bundler; vanilla JS puro |
| Configuración | `config.js` con `API_KEY` y URLs base de los 4 servicios |
| CORS | `CORSMiddleware` habilitado en los 4 microservicios backend |
| Paginación | Consumo de `data.items` en endpoints paginados del backend |
| Manejo errores | Captura HTTP + fallback español; toasts con auto-cierre 5s |

## Decisiones Arquitectónicas Globales
- 4 microservicios FastAPI independientes con SQLite aislada (puertos 8001-8004).
- Comunicación inter-servicios exclusivamente HTTP REST (`httpx`) con `X-API-Key`.
- Frontend consume los 4 microservicios directamente vía `fetch()` con CORS.
- Backend verificado al 100% (301 tests pasando en total).

## Próximos Pasos (Fase 5)
1. 🛑 Usuario: Probar Dashboard en navegador y commit en GitHub.
2. ⬜ Bloque 2: T-25 (Clientes: CRUD + reactivación) y T-26 (Inventario: CRUD).
3. ⬜ Bloque 3: T-27 (Pedidos: formulario orquestador + Saga + listado).
4. ⬜ Bloque 4: T-28 a T-30 (Envíos + estados de entrega + verificación CFs).
