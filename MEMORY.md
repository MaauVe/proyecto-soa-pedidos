# MEMORY.md — Estado del Proyecto SOA: Gestión de Pedidos y Entregas

## Estado Actual
- **Fase**: 5 — cliente-web ✅ COMPLETADA Y VERIFICADA (CF-1 a CF-16)
- **Última tarea**: T-30 ✅ — Verificación integral del frontend y arquitectura SOA
- **Siguiente paso**: Cierre y entrega final del proyecto SOA
- **Fecha de cierre Fase 5**: 2026-11-22

## Decisiones Técnicas — cliente-web (Frontend Completo)
| Decisión | Valor |
|---|---|
| Arquitectura | Single-Page Application (SPA) pura (HTML5, CSS3, ES6+) |
| Dashboard | Monitor en tiempo real con `Promise.allSettled` hacia los 4 microservicios |
| Clientes | CRUD completo, validación de zonas, desactivación y reactivación |
| Inventario | CRUD completo con SKU, stock, precio y peso en kg |
| Pedidos | Orquestación Saga con items dinámicos, selectores y modo degradado |
| Envíos | Listado de guías, visualización y máquina de estados controlada |
| Seguridad | `X-API-Key` y CORS unificado en los 4 servicios FastAPI |

## Resumen del Ecosistema SOA
- **Microservicios (4)**: `clientes` (:8001), `inventario` (:8002), `envios` (:8003), `pedidos` (:8004).
- **Bases de datos**: 4 bases de datos SQLite nativas 100% aisladas.
- **Pruebas backend**: 301 tests automatizados con `pytest` pasando al 100%.
- **Frontend**: SPA pura interactiva servible con cualquier servidor estático.

## Próximos Pasos
1. 🛑 Usuario: Verificación final en el navegador y commit en GitHub de Fase 5.
2. ⬜ Presentación o entrega del Proyecto Final SOA.
