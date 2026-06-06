# Backlog Técnico Accionable para Claude Code

Este backlog está diseñado para ser copiado y entregado directamente a Claude Code (o al equipo de desarrollo). Está ordenado por prioridad estricta. **Las tareas P0 son bloqueantes** y deben implementarse antes de seguir desarrollando features.

---

## 🔴 P0: Infraestructura y Performance Crítica (Bloqueantes)

### 1. Fuga masiva de espacio en disco (50 GB Leak)
**Contexto:** Los despliegues actuales no limpian el caché de Docker. La imagen de Playwright (1.5GB) se acumula en cada deploy, matando el VPS.
**Archivos a modificar:**
* `Makefile`
* `docs/deploy.md`
**Instrucciones para Claude:**
1. En el `Makefile`, ubica el objetivo `prod-deploy` (o similar).
2. Justo después del comando `docker compose -f ... up -d`, agrega las siguientes líneas para limpiar basura automáticamente:
   ```bash
   docker image prune -f
   docker builder prune -f
   ```
3. Actualiza `docs/deploy.md` para reflejar y explicar este comportamiento.

### 2. Cuello de botella en Base de Datos: `COUNT(*)` ineficiente
**Contexto:** Paginar licitaciones hace un `COUNT` sobre un `OUTER JOIN` masivo, lo que traba Postgres y provoca latencia extrema (20s).
**Archivos a modificar:**
* `backend/app/api/v1/licitaciones.py`
**Instrucciones para Claude:**
1. En la función `listar_licitaciones`, elimina o refactoriza el bloque `count_stmt = select(func.count()).select_from(base_stmt.subquery())`.
2. Opciones de solución:
   - **Opción A (Recomendada):** Eliminar el total de la respuesta y usar páginación por cursor o botón "Cargar más" sin devolver el `total_pages`.
   - **Opción B:** Si el total es estrictamente necesario, implementar una función en Postgres para estimar el conteo (`EXPLAIN`), o cachear el conteo base en Redis si los filtros están vacíos.

### 3. SSR Bloqueante en el Dashboard (Pantalla Blanca de 20s)
**Contexto:** Los Server Components en Next.js están esperando peticiones de red pesadas antes de hidratar, dejando al usuario frente a una pantalla vacía.
**Archivos a modificar:**
* `frontend/src/app/(dashboard)/dashboard/page.tsx`
* `frontend/src/app/(dashboard)/licitaciones/page.tsx`
**Instrucciones para Claude:**
1. Importa `<Suspense>` de React.
2. Envuelve los componentes que traen datos (`<KpiCards />`, `<SegmentosChartDynamic />`, `<TopOportunidades />`, `<CierresProximos />`) en límites de Suspense.
3. Crea un componente básico de carga (`<Skeleton />` o un simple `<div>Cargando métricas...</div>`) y asígnalo al `fallback` del Suspense.
4. Asegúrate de que los componentes envueltos sean asíncronos (`async function KpiCards()`) y hagan su fetch por su cuenta sin bloquear el `page.tsx`.

### 4. Riesgo Inminente de OOM Kill (Out of Memory) en Playwright
**Contexto:** Chromium consume >500MB al scrapear PDFs. Un límite de 2GB de RAM con concurrencia de 2 en Celery provocará la muerte silenciosa del contenedor.
**Archivos a modificar:**
* `docker-compose.prod.yml`
**Instrucciones para Claude:**
1. En el servicio `worker_scraper`, cambia la concurrencia en el comando de Celery de `--concurrency=2` a `--concurrency=1`.
2. O, alternativamente, sube el límite de memoria a `4g` en la sección `deploy.resources.limits.memory` si el VPS lo permite.

---

## 🟠 P1: Experiencia de Usuario y Red Interna (Alta Prioridad)

### 5. Secuestro de Red en el Middleware de Next.js
**Contexto:** El `middleware.ts` hace un `fetch` hacia FastAPI de forma síncrona para refrescar el token en cada transición de página, duplicando la latencia.
**Archivos a modificar:**
* `frontend/src/middleware.ts`
* (Crear nuevo) interceptor de Axios/Fetch o Hook de estado.
**Instrucciones para Claude:**
1. En `middleware.ts`, elimina el bloque donde se hace `fetch(INTERNAL_API_URL + "/api/v1/auth/refresh")`.
2. El middleware solo debe revisar la fecha de expiración (`exp`) decodificando el JWT sin validación criptográfica (para velocidad) y redirigir al login si ya expiró el refresh.
3. El refresco del token (rotación) debe ocurrir asincrónicamente del lado del cliente o en llamadas Server Actions controladas que fallen gracefully con 401.

---

## 🟡 P2: Deuda Técnica y Optimización (Prioridad Media)

### 6. Destrucción de I/O en Bulk Inserts (Triggers)
**Contexto:** El trigger que actualiza el vector de búsqueda corre en cada insert, ahogando los scripts de backfill de datos.
**Archivos a modificar:**
* `schema.sql` (o crear migración de Alembic en backend)
**Instrucciones para Claude:**
1. Elimina la función `fn_licitaciones_update_search_vector()` y su respectivo `TRIGGER`.
2. Modifica la columna `search_vector` de la tabla `licitaciones` para que use generación automática de Postgres 12+: 
   ```sql
   search_vector tsvector GENERATED ALWAYS AS (to_tsvector('spanish', coalesce(nombre, '') || ' ' || coalesce(descripcion, ''))) STORED;
   ```
3. Si usas migraciones de Alembic, genera la migración correspondiente para este drop+alter.

### 7. Limpieza de Superficie de Ataque
**Contexto:** Contenedores de desarrollo (`flower`, `mailhog`) existen en los YAMLs de producción.
**Archivos a modificar:**
* `docker-compose.prod.yml`
**Instrucciones para Claude:**
1. Elimina completamente las entradas de `flower` y `mailhog`. En Docker Compose para producción, lo que no se usa simplemente no debe estar en el archivo. No dependas de `profiles: ["never"]` en ambientes pro.
