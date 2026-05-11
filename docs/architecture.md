# Decisiones Arquitectónicas — Radar Público

Registro de ADRs (Architecture Decision Records) del proyecto.
Formato: Contexto → Decisión → Consecuencias → Alternativas descartadas.

---

## ADR-001: Autenticación propia con FastAPI

**Estado:** Aceptado  
**Fecha:** 2026-05-09  
**Sprint:** 1

### Contexto

Radar Público requiere autenticación para dos roles: `admin` (operador interno) y `proveedor` (cliente empresa). El modelo de negocio es **invitación-only** — no hay auto-registro. Las cuentas las aprovisiona el admin tras recibir pago externo.

Restricciones relevantes:
- Sin self-service signup
- MFA obligatorio solo para admin (TOTP), no para proveedores en v1
- Stack: FastAPI + Postgres + Redis — ya presentes en el proyecto
- Todas las dependencias de auth (`python-jose`, `passlib`, `redis`) ya estaban en `requirements.txt`

### Decisión

Implementar autenticación propia en FastAPI con:
- **bcrypt cost 12** para passwords (passlib)
- **JWT HS256** de 15 min para access tokens
- **Refresh tokens rotativos** de 7 días, hasheados SHA-256 en `refresh_tokens`
- **Password reset tokens** de 30 min, single-use, en `password_reset_tokens`
- **Rate limiting fixed window** con Redis INCR+EXPIRE (5 req/15 min en login)
- **Lockout a nivel BD** tras 5 intentos fallidos (`locked_until = now() + 30 min`)
- **Auditoría** en `eventos_auditoria` — sin PII, solo user_id

### Consecuencias

**Positivas:**
- Sin dependencia de servicio externo (no hay SPOF externo ni costo adicional)
- Control total sobre el flujo de onboarding y reset
- Compatible con el modelo invitación-only desde el día 1
- Fácil de auditar y adaptar a requerimientos regulatorios chilenos (Ley 19.628)

**Negativas:**
- Mantenemos código de auth propio — mayor responsabilidad de seguridad
- MFA TOTP para admin requiere implementación separada (Sprint 6)
- No hay integración con IdP externo (SAML, OIDC) si se necesita en futuro

### Alternativas descartadas

| Alternativa | Motivo de descarte |
|-------------|-------------------|
| **Clerk** | Diseñado para self-service con planes gratuitos; sobre-ingeniería para modelo invitación-only |
| **Auth.js (NextAuth)** | Orientado a frontend Next.js; no cubre el backend FastAPI de forma nativa |
| **Supabase Auth** | Agrega dependencia de plataforma; complejidad innecesaria dado el stack existente |

---

## ADR-002: Rate limiting fixed window vs sliding window

**Estado:** Aceptado  
**Fecha:** 2026-05-09  
**Sprint:** 1

### Decisión

Fixed window con Redis `INCR` + `EXPIRE` para el endpoint `/auth/login`.

### Justificación

La regla de oro #6 pide "5 intentos / 15 min por IP". El edge case del fixed window (hasta 2× el límite entre ventanas adyacentes) es aceptable porque la segunda línea de defensa — el lockout a nivel BD tras 5 fallos (`locked_until`) — cubre el caso límite. La defensa es en capas, no monolítica en Redis.

Sliding window con `ZSET` agrega precisión que no necesitamos y ~3× el costo de Redis por operación.

---

## ADR-003: Método de backfill histórico — API por fecha, no Datos Abiertos

**Estado:** Aceptado  
**Fecha:** 2026-05-10  
**Sprint:** 1 (descubierto durante implementación)

### Contexto

El roadmap y la regla de oro #16 original asumían que el backfill histórico de licitaciones se haría descargando CSVs masivos desde `datos-abiertos.chilecompra.cl`, evitando así consumir la cuota diaria de la API (10.000 req/día por ticket).

Durante el Sprint 1 se validó esta hipótesis y resultó incorrecta.

### Descubrimiento

El portal `datos-abiertos.chilecompra.cl` es una SPA React que sirve **visualizaciones analíticas** vía API REST interna (`mserv-datos-abiertos.chilecompra.cl`). Las "descargas" disponibles son:
- Por organismo específico (no dumps anuales globales)
- Requieren contexto de sesión autenticada
- No existe un catálogo de archivos accesible públicamente sin autenticación

No hay CSVs de licitaciones con descarga directa pública equivalente a los que asumía el roadmap.

### Decisión

Implementar el backfill histórico usando el **endpoint de listado por fecha** de la API oficial de ChileCompra (`/licitaciones.json?fecha=DDMMAAAA`), con las siguientes restricciones:

- **1 request por fecha consultada** (el endpoint retorna todas las licitaciones publicadas ese día)
- **Ventana nocturna obligatoria:** 22:00–07:00 CLT (regla de oro #17)
- **Rate limit interno:** 5 req/s con backoff exponencial (regla de oro #18)
- **Idempotencia garantizada:** upsert con hash SHA-256 del contenido, ON CONFLICT en BD (regla de oro #29)
- **Implementación:** `app/scripts/backfill.py` — `--months N` para definir rango histórico

### Estimación de consumo

Con `--months 6` (180 días): **180 requests** = 1.8% de la cuota diaria.  
Con `--months 24` (720 días): **720 requests** = 7.2% de la cuota diaria.  
El backfill completo de 2 años cabe en una única noche sin comprometer la sincronización diurna.

### Consecuencias

**Positivas:**
- Implementación simple — un loop sobre fechas con el cliente HTTP ya existente
- Consumo de cuota mínimo (~180 req para 6 meses vs 10.000 disponibles)
- Completamente idempotente: se puede interrumpir y retomar sin duplicados

**Negativas:**
- Dependencia de la API oficial (si cambia el formato de fecha o el endpoint, el backfill falla)
- Sin fuente alternativa offline; si la cuota se agota, hay que esperar al día siguiente
- El detalle completo de licitaciones históricas requiere una segunda pasada (`obtener_detalle`) — el backfill inicial solo carga info básica

### Alternativas descartadas

| Alternativa | Motivo de descarte |
|---|---|
| CSVs de Datos Abiertos | No existen con descarga pública para licitaciones |
| Scraping del portal Mercado Público | Viola TOS, riesgo de bloqueo, complejidad innecesaria para datos que la API sí entrega |
| Comprar datos históricos a terceros | Sin proveedores conocidos confiables; costo injustificado |

---

## ADR-004: Sincronización de detalle — trigger, política de caché y manejo de 404

**Estado:** Aceptado  
**Fecha:** 2026-05-11  
**Sprint:** 2

### Contexto

El patrón obligatorio de ChileCompra es **lista → detalle**: la sincronización diaria trae
info básica (código, nombre, estado, fecha de cierre) de cada licitación activa. El detalle
completo (descripción, organismo, monto, items, criterios de evaluación, calendario de fechas)
requiere una segunda llamada por código.

Sprint 2 implementa esa segunda llamada como tarea Celery independiente. Había que decidir:
1. **Cuándo disparar** la sincronización de detalle.
2. **Cuándo omitir** el detalle ya sincronizado (evitar cuota innecesaria — regla de oro #21).
3. **Qué hacer con 404** (licitación ya no existe en ChileCompra).

### Decisión

**Trigger:** `sync_listado_diario` encola `sync_detalle_licitacion.delay(codigo)` inmediatamente
tras cada licitación nueva o cuyo hash haya cambiado. No bloquea — el detalle se procesa en background.
Las licitaciones sin cambio NO se encolan (regla de oro #21 — cache agresivo).

Cuando `sync_listado_diario` detecta un hash cambiado en una licitación existente, setea
`detalle_sincronizado_at = NULL` antes de encolar, forzando que `sync_detalle_licitacion`
re-sincronice el detalle aunque `detalle_sincronizado_at` hubiera estado poblado.

**Política de caché en `sync_detalle_licitacion`:** si `detalle_sincronizado_at` ya está
poblado → retornar `sin_cambio` sin llamar a la API. Si `NULL` (nueva o hash cambiado desde
el listado) → sincronizar.

**Política 404:** loguear `no_encontrada=1`, no elevar excepción, dejar `detalle_sincronizado_at`
en NULL. El 404 es semántico (licitación revocada/eliminada) — no es un error transitorio que
justifique reintentos automáticos.

### Consecuencias

**Positivas:**
- Cuota controlada: solo se consulta el detalle cuando hay algo nuevo que sincronizar.
- La tarea es idempotente: delete + insert para items (en lugar de upsert parcial), upsert por tipo para fechas.
- 404 silencioso evita colas de reintentos para licitaciones que nunca se recuperarán.

**Negativas:**
- Un hash del listado puede no capturar cambios en el detalle (ej: cambio en items sin cambio de nombre/estado). Se acepta como trade-off; la siguiente sincronización de listado que detecte cambio de estado forzará un nuevo detalle.
- `unspsc_codigos` debe existir en la BD antes de insertar items con `CodigoProducto` válido. Si no existe, la FK falla silenciosamente en tests unitarios (se usa `CodigoProducto=None` en mocks).

### Alternativas descartadas

| Alternativa | Motivo de descarte |
|---|---|
| Trigger por schedule propio (cada N minutos) | Consumo de cuota no controlado; consulta el detalle aunque no haya cambios |
| Agregar en el mismo archivo `sync_chilecompra.py` | Sin precedente de múltiples tareas por archivo en el repo; `celery_app.py` ya reservaba `app.tasks.sync_detalle` |
| Upsert parcial para items (INSERT ON CONFLICT UPDATE) | La lista de items puede cambiar en largo y posición; delete + insert es más correcto y simple |
