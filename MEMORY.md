# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 5 — cliente-web (En progreso: Bloque 3 completado)
- **Última tarea**: T-27 ✅ — Sección Pedidos con Saga, items dinámicos y cancelación
- **Siguiente paso**: Bloque 4 — T-28 a T-30 (Envíos, estados y verificación CFs)
- **Fecha**: 2026-11-22

## Decisiones Técnicas — cliente-web
| Decisión | Valor |
|---|---|
| Arquitectura | Single-Page Application (SPA) pura (HTML5, CSS3, ES6+) |
| Clientes | Listado con badges, alta con zona, detalle modal, desactivar/reactivar |
| Inventario | Listado con SKU/stock/peso, alta completa, edición modal, detalle |
| Pedidos | Formulario con items dinámicos, selectores dinámicos, Saga, detalle degradado |
| Modales | Sistema de modal reutilizable con backdrop y tecla Escape |
| Paginación | Consumo de `data.items` en endpoints paginados del backend |
| Manejo errores | Captura HTTP + fallback español; toasts con auto-cierre 5s |

## Decisiones Arquitectónicas Globales
- 4 microservicios FastAPI independientes con SQLite aislada (puertos 8001-8004).
- Comunicación inter-servicios exclusivamente HTTP REST (`httpx`) con `X-API-Key`.
- Frontend consume los 4 microservicios directamente vía `fetch()` con CORS.
- Backend verificado al 100% (301 tests pasando en total).

## Próximos Pasos (Fase 5)
1. 🛑 Usuario: Probar Sección Pedidos en navegador y commit en GitHub.
2. ⬜ Bloque 4: T-28 (Envíos: listar, detalle, transición de estados).
3. ⬜ Bloque 4: T-29 y T-30 (Pulido final de feedback visual y verificación CF-1 a CF-16).
