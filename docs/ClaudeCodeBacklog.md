# Backlog Técnico Accionable para Claude Code

Este backlog refleja el estado de las correcciones del proyecto. Las tareas marcadas como completas han sido resueltas en sesiones previas o implementadas por Claude Code en esta corrida.

---

## 🟢 Tareas Completadas (Verificadas)

- **[x] Tarea 1: Falla silenciosa del ticket inactivo en Mercado Público (P0)**
  - *Estado:* Completado por Claude Code.
  - *Fix:* `_raise_for_status` lanza `TicketInvalidoError` cuando la API devuelve un mensaje de ticket inactivo en HTTP 200 OK. Tests unitarios añadidos y pasando.
- **[x] Tarea 2: Persistencia del Ticket en Onboarding de Proveedores (P0)**
  - *Estado:* Completado por Claude Code.
  - *Fix:* `/ticket-request` en `empresa.py` cifra y persiste el ticket en BD con estado `pending`, gatillando la tarea asíncrona Celery `validate_ticket_api` para validarlo y pasarlo a `active` o `error`.
- **[x] Tarea 3: Encolamiento Celery síncrono en listados de licitaciones (P0)**
  - *Estado:* Completado por Claude Code.
  - *Fix:* Removidas las llamadas bloqueantes a `celery_app.send_task` dentro de `listar_licitaciones` en `licitaciones.py`.
- **[x] Tarea 5: Fuga de espacio en disco en deploys (P0)**
  - *Estado:* Ya estaba implementado en `Makefile` con comandos de purga de imágenes y constructores.
- **[x] Tarea 6: SSR bloqueante en el Dashboard (P1)**
  - *Estado:* Ya estaba implementado en `frontend/src/app/(dashboard)/dashboard/page.tsx` con límites de React `<Suspense>` para componentes de carga diferida.
- **[x] Tarea 7: Secuestro de Red en el Middleware de Next.js (P1)**
  - *Estado:* Ya estaba resuelto en `frontend/src/middleware.ts` eliminando las llamadas bloqueantes a la red interna y pasándolas a validación estática del cliente.
- **[x] Tarea 8: Límite de Memoria OOM en Scrapers (P1)**
  - *Estado:* Ya estaba implementado en `docker-compose.prod.yml` con `--concurrency=1` para Playwright.
- **[x] Tarea 9: Optimizar Triggers de Búsqueda Full Text (P2)**
  - *Estado:* Ya estaba resuelto mediante la columna generada nativa `STORED` en Postgres en `schema.sql` y las migraciones de Alembic correspondientes.

---

## 🔴 Tareas Pendientes (Genuinas)

### Tarea 4 — Cuello de botella en Base de Datos: `COUNT(*)` ineficiente en paginación
* **Severidad:** Media
* **Prioridad:** P1
* **Archivos a modificar:**
  * `backend/app/api/v1/licitaciones.py` (método `listar_licitaciones`)
  * `backend/app/api/v1/pipeline.py` (método `listar_pipeline`)
* **Contexto:** 
  Ambos endpoints ejecutan `count_stmt = select(func.count()).select_from(base_stmt.subquery())` sobre subconsultas complejas de SQL para calcular la paginación clásica. Esto obliga a Postgres a escanear de forma secuencial grandes conjuntos de filas, destruyendo el rendimiento de navegación cuando el volumen de base de datos crece.
* **Instrucciones para Claude:**
  1. En `licitaciones.py` y `pipeline.py`, remover el cálculo del total basado en `subquery().count()`.
  2. Implementar una de estas opciones para acelerar la latencia:
     - **Opción A (Recomendada):** Paginación por cursor o devolver un booleano `has_next` (evaluando `limit(page_size + 1)` y descartando el último ítem en la respuesta) para que el frontend renderice botones "Anterior/Siguiente" o "Cargar más" sin requerir un `COUNT` exacto de filas en Postgres.
     - **Opción B:** Si el total exacto es imprescindible, estimar la cantidad usando planes de ejecución (`EXPLAIN`) de Postgres o almacenar el conteo base en Redis con un TTL de 15 minutos.
