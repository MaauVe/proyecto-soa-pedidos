# Constitución del Proyecto SOA — Principios Innegociables

> Estos principios son la ley del proyecto. Ninguna excepción sin consenso explícito.

## P1 — Independencia y Bajo Acoplamiento
Cada servicio es una unidad autónoma: no importa código de otro servicio.
La comunicación entre servicios ocurre **únicamente por HTTP REST**.

## P2 — Aislamiento de Datos
Cada servicio posee y gestiona **su propia base de datos SQLite**.
Ningún servicio accede directamente a la BD de otro.

## P3 — Spec-Driven Development (SDD)
**Nada se programa sin una `spec.md` aprobada**, un plan y una tarea registrada.
Orden obligatorio: Spec → Plan → Tarea → Prueba → Implementación.

## P4 — Tolerancia a Fallos y Validación Estricta
Todos los modelos de entrada/salida usan **Pydantic**.
El orquestador captura siempre `TimeoutException` y `HTTPStatusError` de `httpx`.
Los errores se retornan con mensajes claros en español y códigos HTTP correctos.

## P5 — Seguridad: Sin Secretos en Git
Claves, tokens y URLs de entorno viven **sólo en `.env`** (excluido por `.gitignore`).
El header `X-API-Key` es obligatorio en todos los endpoints protegidos.

## P6 — Idioma y Pruebas Automatizadas
Código, variables y endpoints en **inglés**. Mensajes al usuario y documentación en **español**.
Toda funcionalidad debe tener pruebas `pytest` que pasen antes de considerarse terminada.
