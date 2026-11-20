# AGENTS.md — Proyecto SOA: Gestión de Pedidos y Entregas

## Resumen del Proyecto
Sistema de integración empresarial con 4 microservicios FastAPI + frontend HTML/CSS/JS puro.
Cada servicio es autónomo, tiene su propia BD SQLite y se ejecuta localmente sin Docker.

## Mapa de Puertos y Carpetas
| Servicio             | Puerto | Base de Datos    | Carpeta               |
|----------------------|--------|------------------|-----------------------|
| servicio-clientes    | 8001   | clientes.db      | servicio-clientes/    |
| servicio-inventario  | 8002   | inventario.db    | servicio-inventario/  |
| servicio-envios      | 8003   | envios.db        | servicio-envios/      |
| servicio-pedidos     | 8004   | pedidos.db       | servicio-pedidos/     |
| cliente-web          | —      | —                | cliente-web/          |

## Reglas de Arquitectura SOA
1. Cada servicio es **completamente independiente**: sin imports cruzados entre servicios.
2. Cada servicio gestiona **su propia BD SQLite** aislada; nunca comparte datos directamente.
3. Todo servicio expone **Swagger/OpenAPI automático** vía FastAPI (`/docs`, `/redoc`).
4. Los endpoints protegidos exigen el header **`X-API-Key`**; rechazar con 401 si falta o es inválido.
5. `servicio-pedidos` es el orquestador: llama a los demás **sólo por HTTP** con `httpx`.
6. Nunca hardcodear URLs ni claves; usar siempre variables de entorno (`.env` + `python-dotenv`).

## Convenciones de Código
- **Inglés**: nombres de variables, funciones, clases, endpoints, campos de BD y JSON.
- **Español**: mensajes de error al cliente, docstrings de servicios, textos de UI y documentación.
- Formato: snake_case para variables/funciones, PascalCase para clases Pydantic y modelos.
- Cada servicio tiene su propio `requirements.txt` y `main.py` como punto de entrada.

## Flujo Obligatorio SDD (Spec-Driven Development)
1. **Leer** `docs/constitution.md` y `MEMORY.md` antes de cualquier acción.
2. **Revisar** la spec aprobada en `specs/` antes de escribir código.
3. **Nunca implementar** nada que no esté en una `spec.md` aprobada y confirmada.
4. **Una tarea a la vez**: tomar una tarea de `tasks.md`, escribir pruebas `pytest` primero,
   implementar hasta que pasen, luego detenerse para revisión.
5. **Stop obligatorio** al finalizar cada tarea: reportar resultado y esperar aprobación.

## Regla de Memoria
- Actualizar `MEMORY.md` al finalizar cada fase o tarea importante.
- Mantener `MEMORY.md` **por debajo de 50 líneas** en todo momento.
- **Nunca guardar** claves, tokens ni contraseñas reales en `MEMORY.md` ni en ningún archivo Git.
