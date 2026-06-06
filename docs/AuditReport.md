# Auditoría técnica brutal del proyecto

## 1. Resumen ejecutivo

El proyecto se encuentra **en estado riesgoso** y **NO está listo para producción masiva**.

Aunque las bases arquitectónicas (FastAPI + Next.js + Celery + Postgres) son correctas y se nota que hubo un diseño previo, la implementación actual sufre de un claro problema de "fuerza bruta" generada por IA. El sistema funciona en el caso feliz, pero falla estrepitosamente en el manejo de recursos e IO. 

Los problemas que reportas (50 GB ocupados y 20 segundos de cold start) no son un misterio: son la consecuencia directa de una falta de estrategia de retención de Docker, y un frontend Next.js que bloquea su SSR esperando consultas pesadas sin optimizar (COUNT masivos) en Postgres. Si subes usuarios reales a este sistema hoy, los workers de Playwright colapsarán la RAM y la base de datos se ahogará con las búsquedas no indexadas.

## 2. Diagnóstico general

* Arquitectura: **6/10** (Buena separación de servicios, pero mala asignación de responsabilidades de carga).
* Backend: **7/10** (Código limpio, buena abstracción, pero queries destructivas en rendimiento).
* Frontend: **4/10** (Uso ineficiente del App Router, sin Suspense, middleware bloqueante).
* Base de datos: **7/10** (Buen uso de pgvector y constraints, pero falta estrategia para tablas grandes).
* Seguridad: **8/10** (Buen manejo criptográfico de los tickets de ChileCompra y JWTs propios).
* Documentación: **9/10** (Excelente spec y ADRs, aunque el código ya se está desviando).
* Calidad de código: **7/10** (Limpio en backend, pero el frontend carece de manejo de estados de carga resilientes).
* Mantenibilidad: **5/10** (Imágenes Docker pesadísimas, deploys destructivos, falta de scripts de purga).

## 3. Hallazgos críticos

### Hallazgo 1 — Fuga masiva de espacio en disco (El problema de los 50 GB)
* **Severidad:** Crítica
* **Archivo(s):** `Makefile`, `docs/deploy.md`, `docker-compose.prod.yml`
* **Evidencia:** El comando `make prod-deploy` ejecuta un `docker compose build` de todo, incluida la imagen del worker de Playwright (que pesa ~1.5 GB). No hay ningún paso que limpie las imágenes huérfanas (`dangling images`).
* **Problema:** Cada deploy deja en disco la imagen de Playwright, Node y Python anterior. Tras 15-20 deploys, el disco se llena de basura.
* **Impacto:** El VPS se queda sin inodos/espacio. Postgres falla al escribir en el disco, botando la base de datos.
* **Recomendación:** Agregar sistemáticamente `docker image prune -f` y `docker builder prune -f` en el comando del Makefile post-deploy.
* **Prioridad:** P0

### Hallazgo 2 — SSR bloqueante y Queries lentas (El problema de los 20 segundos)
* **Severidad:** Crítica
* **Archivo(s):** `frontend/src/app/(dashboard)/dashboard/page.tsx`, `backend/app/api/v1/licitaciones.py`
* **Evidencia:** Next.js ejecuta `KpiCards` y listas en el servidor de forma síncrona. A su vez, `licitaciones.py` ejecuta `select(func.count()).select_from(base_stmt.subquery())`. 
* **Problema:** En Postgres, hacer `COUNT(*)` con `OUTER JOIN` sobre una tabla de miles o millones de registros requiere un escaneo secuencial. El backend tarda segundos en responder, y como el frontend no usa `<Suspense>`, bloquea toda la pantalla dejándola en blanco hasta que la API responde.
* **Impacto:** Experiencia de usuario inaceptable. Pareciera que el sistema está caído.
* **Recomendación:** 
  1. Frontend: Usar React `<Suspense fallback={<Skeleton />}>` para envolver los componentes de datos.
  2. Backend: No hacer COUNT exactos en listas masivas; usar estimaciones de Postgres o cachear los totales en Redis.
* **Prioridad:** P0

### Hallazgo 3 — OOM Killer inminente por concurrencia de Playwright
* **Severidad:** Alta
* **Archivo(s):** `docker-compose.prod.yml`
* **Evidencia:** El servicio `worker_scraper` tiene un límite de recursos de `memory: 2g`, pero el comando es `celery --concurrency=2` sobre una imagen de Playwright.
* **Problema:** Cada proceso Chromium levanta fácilmente 400-600MB de RAM. Sumado a los 2 workers de Python, rozan el límite de 2GB. Al parsear un PDF pesado de Mercado Público, Docker matará el proceso (OOM Kill).
* **Impacto:** Tareas de scraping que nunca terminan (zombies) o se reintentan infinitamente agotando la cuota y CPU.
* **Recomendación:** Bajar la concurrencia a `--concurrency=1` si mantienes el límite de 2GB, o subir la memoria a 4GB en el `docker-compose.prod.yml`.
* **Prioridad:** P0

### Hallazgo 4 — Middleware de Next.js secuestra la red
* **Severidad:** Alta
* **Archivo(s):** `frontend/src/middleware.ts`
* **Evidencia:** Hace `await fetch(INTERNAL_API_URL + "/api/v1/auth/refresh")` de forma síncrona dentro del middleware.
* **Problema:** Esto bloquea todas las transiciones de página (incluso las prefetched). Si la red interna de Docker tiene latencia o el backend está saturado procesando algo, la navegación entera del frontend se paraliza.
* **Impacto:** Degradación artificial del performance del lado del cliente.
* **Recomendación:** Eliminar el fetch del middleware. El middleware solo debe revisar la expiración por decode; el refresh se debe hacer asincrónicamente mediante Server Actions o un hook del lado del cliente (Axios interceptor).
* **Prioridad:** P1

## 4. Diferencias entre documentación y código

| Requisito documentado | Estado real en código | Evidencia | Riesgo | Acción recomendada |
| :--- | :--- | :--- | :--- | :--- |
| **Auth Provider** (Spec.md dice Auth.js vs Clerk) | Implementación propia | `app/api/v1/auth.py` tiene JWT propio. Confirmado por `ADR-001`. | Bajo | Actualizar el `spec.md` para reflejar la decisión tomada en el ADR. |
| **Roles de usuario multi-empresa** (Spec v2) | A medias | El modelo tiene roles, pero la tabla `empresas` asume 1 usuario por 1 empresa. | Medio | Afectará fuertemente la Fase 2 si no se extrae la relación a una tabla pivote `usuarios_empresas` a futuro. |
| **Integración Resend (Email)** | No implementada | Hay una carpeta `email` pero no encontré implementaciones reales que usen `RESEND_API_KEY`. | Medio | No se enviarán los passwords temporales de los usuarios creados por el admin. |
| **Rate limit de ChileCompra (10.000 req/día)** | Parcial | El ticket se encripta, pero el contador de `api_quota_log` no corta los scripts en tiempo real. | Alto | Si un backfill falla y entra en retry, quemará la cuota diaria del cliente sin cortarse. |

## 5. Problemas de arquitectura

**Caché inexistente para KPIs:**
Estás usando Postgres como una calculadora OLAP para mostrar métricas en tiempo real en un dashboard B2B. Los agregados (como el gráfico de segmentos y el pipeline) deben ser calculados asíncronamente (ej: un Celery beat cada 15 min) y almacenados en Redis o en una tabla `materialized view`. Hacer `COUNT` y `SUM` en cada render de página es un suicidio de escalabilidad.

**Delegación de Auth a Next.js:**
Tener Next.js haciendo refresh tokens en su capa de middleware hacia FastAPI crea un acoplamiento temporal muy tenso. Next.js App Router prefiere Server Components con cookies administradas por él mismo (NextAuth/Auth.js). Haber inventado Auth propio en FastAPI obliga al frontend a hacer contorsiones anti-patrón.

## 6. Problemas de seguridad

1. **Denegación de servicio (DoS) por Búsqueda Full Text:** `q` (búsqueda) se pasa a Postgres. Una búsqueda muy compleja (ej: strings larguísimos con caracteres extraños) puede forzar un pegazo de CPU en la BD. *Prioridad: P2.*
2. **Encriptación de tickets es ciega:** La columna `ticket_cifrado` no tiene rotación de llaves, pero está okay para un MVP.

## 7. Problemas de base de datos

1. **Triggers Pesados (P0):** `trg_licitaciones_search_vector` ejecuta `to_tsvector` en CADA `INSERT` o `UPDATE` de la tabla de licitaciones. Al hacer el backfill histórico masivo, esto va a consumir un volumen brutal de CPU en Postgres. Debería ser una columna almacenada generada automáticamente (`GENERATED ALWAYS AS ... STORED`), soportado nativamente en Postgres sin necesidad de triggers lentos de PL/pgSQL.
2. **Fragmentación del Pipeline:** El estado de un ítem (`PipelineItem.estado`) está en una tabla separada, lo cual está bien, pero las búsquedas combinadas del usuario (mis intereses + que no las haya descartado en mi pipeline) requerirán `NOT EXISTS` o `LEFT JOIN` masivos que no están indexados correctamente para esas condiciones compuestas.

## 8. Problemas de frontend

1. **Falta de Streaming (P0):** El layout y las páginas se rinden como un gran bloque monolítico de HTML síncrono. Debes implementar `loading.tsx` y `<Suspense>` en componentes clave.
2. **Uso de TanStack Query vs Server Components:** Tienes dependencias de `zustand` y `tanstack/react-query`, pero parece que están usando mucho RSC (React Server Components). Deben definirse claramente las fronteras: carga inicial por RSC, mutaciones por Server Actions o React Query. La mezcla no está madura.

## 9. Problemas de backend

1. **Pagination offset-limit (P1):** La API usa `offset((page - 1) * page_size)`. Para la página 1000, la base de datos debe escanear y descartar 25.000 filas. Es un conocido asesino de performance (Slow Offset). Considera usar *Cursor Pagination* basada en `fecha_publicacion` o limitar arbitrariamente las páginas máximas.
2. **Acoplamiento Síncrono-Asíncrono:** En `licitaciones.py` haces `celery_app.send_task` dentro del loop que genera los responses del JSON. Esto añade milisegundos de latencia a cada item en la lista. Debería hacerse en batch (`celery_app.send_task(..., args=[list_of_ids])`).

## 10. Código innecesario o sospechoso

* **`mailhog` y `flower` en infra de despliegue:** Aunque tienen profile `never`, tenerlos en los archivos `.yml` que revisa DevOps agrega confusión de superficies de ataque. Deberían estar solo en `docker-compose.yml` (dev) y ausentes totalmente en `docker-compose.prod.yml`.
* **Archivos vacíos o no usados:** La carpeta `frontend/src/app/(auth)` tiene un montón de páginas, asumo que todas están pegando al Auth custom, pero deberías auditar si no estás reescribiendo la rueda de Auth.js inútilmente.

## 11. Plan de corrección recomendado

### P0 — Corregir antes de seguir desarrollando
* **Descripción:** Implementar purga de Docker en deploy.
* **Motivo:** Evitar que el VPS colapse a los pocos días por espacio en disco.
* **Archivos:** `Makefile`.
* **Complejidad:** Baja (Añadir `docker image prune -f`).

* **Descripción:** Refactor de componentes Server a `<Suspense>`.
* **Motivo:** Eliminar la pantalla blanca de 20 segundos.
* **Archivos:** `dashboard/page.tsx`, `licitaciones/page.tsx`.
* **Complejidad:** Media.

* **Descripción:** Eliminar el `COUNT(*)` incondicional o usar `EXPLAIN` count estimate.
* **Motivo:** Eliminar el cuello de botella de Postgres que traba las peticiones del dashboard.
* **Archivos:** `backend/app/api/v1/licitaciones.py`, `backend/app/api/v1/pipeline.py`.
* **Complejidad:** Media.

### P1 — Corregir antes de pruebas con usuarios
* **Descripción:** Bajar la concurrencia de Playwright a 1.
* **Motivo:** Evitar OOM Killers.
* **Archivos:** `docker-compose.prod.yml`.
* **Complejidad:** Baja.

* **Descripción:** Migrar refresh token auth fuera del middleware Next.js.
* **Motivo:** Reducir latencia artificial de red.
* **Archivos:** `middleware.ts`, un nuevo hook de Axios/Fetch interceptor.
* **Complejidad:** Alta.

### P2 — Corregir antes de producción
* **Descripción:** Migrar trigger `trg_licitaciones_search_vector` a columnas `GENERATED ALWAYS STORED`.
* **Motivo:** Eficiencia de escritura masiva en base de datos.
* **Archivos:** `schema.sql`.
* **Complejidad:** Baja.

### P3 — Mejoras posteriores
* **Descripción:** Implementar caché de Redis para los KPIs del Dashboard.
* **Complejidad:** Alta.

## 12. Preguntas que debería responder Claude Code

Para forzar a la IA que construyó esto a arreglarlo sin romper nada, pregúntale:

1. *"En `licitaciones.py` estás haciendo `select(func.count()).select_from(...)` sobre una tabla de millones de registros para la paginación. ¿Por qué tomaste esta decisión sabiendo que Postgres hace Sequential Scans lentísimos con esto? Dame el código para cambiar esto a limitación por cursor o estimación de conteos."*
2. *"El SSR del frontend tarda 20 segundos. Estás bloqueando el render en `dashboard/page.tsx` esperando al backend. ¿Por qué no utilizaste React Suspense y Skeletons? Modifica `dashboard/page.tsx` para solucionar este bloqueo de hidratación."*
3. *"En el `middleware.ts` pusiste un `fetch` a la API interna para el refresh token. ¿Eres consciente de que eso agrega latencia de red intra-docker a cada request protegido antes de renderizar la página? Propón un rediseño que use un interceptor del cliente y Server Actions optimistas."*
4. *"En el `docker-compose.prod.yml`, le pusiste 2 GB de límite de RAM al worker de Playwright pero corres `celery --concurrency=2`. Sabiendo que Chromium consume al menos 500MB en uso real, esto puede crashear. Ajusta estos parámetros para evitar un OOM."*

## 13. Veredicto final

**¿El proyecto está bien encaminado?**
Sí, estructuralmente es un buen diseño. Las piezas correctas (Postgres, Redis, Next.js, FastAPI, Celery) están presentes. El modelo de datos tiene sentido y resuelve bien el problema del negocio B2B de ChileCompra.

**¿Qué parte es más débil?**
El manejo de performance y SSR. El código fue generado asumiendo una base de datos con 10 registros (escenario ideal), no la realidad de la API de ChileCompra con millones de datos históricos.

**¿Qué parte debe rehacerse?**
La capa de obtención de datos del frontend. Las páginas no deben esperar llamadas asíncronas para entregar HTML al cliente. Debes pasarlas a `<Suspense>` inmediatamente. El middleware no debe hacer llamadas de red bloqueantes.

**¿Qué parte se puede conservar?**
El Backend de FastAPI (rutas, endpoints, servicios) es bastante sólido. El diseño de la base de datos es robusto. El Worker de Python está bien estructurado.

**¿Cuál es el mayor riesgo si sigo construyendo encima de esto?**
Si sigues agregando features (como IA o el Chatbot) sin arreglar la paginación lenta y el problema de los Docker dangling images, tu servidor VPS de 50 GB se apagará en producción en la primera semana de uso real, y la plataforma parecerá inusable por su lentitud. **Frena el desarrollo de nuevas features y dedica el próximo sprint a optimizar latencia, infraestructura y memoria.**
