# Sprint 2 — Sincronización de detalle de licitaciones

> Prompt de sesión. Pegalo al inicio de una nueva conversación con Claude Code para arrancar Sprint 2 sin perder contexto.

---

## Contexto del proyecto

**Radar Público** es una plataforma SaaS B2B de inteligencia comercial sobre Mercado Público de Chile. Stack: FastAPI 0.115 + SQLAlchemy 2.0 async + PostgreSQL 16 + Redis 7 + Celery 5.4. Repositorio en `/proyectos/radar-publico`.

**Estado actual (2026-05-10):**
- Sprint 1 cerrado y commiteado en `main`.
- Tareas operacionales post-Sprint 1 resueltas: bugfix en `backfill.py`, regla de oro #16 reformulada en `CLAUDE.md`, ADR-003 documentado en `docs/architecture.md`.
- Engram actualizado con la sesión anterior.

**Comenzar la sesión con:**
```python
mem_context(project="radar-publico")   # recupera contexto de sesiones anteriores
```

---

## Objetivo de esta sesión

Implementar la **sincronización de detalle de licitaciones** (Sprint 2, primera unidad de trabajo).

El patrón obligatorio de ChileCompra es **lista → detalle**: la sincronización diaria trae info básica de cada licitación; el detalle completo (items, criterios de evaluación, fechas, bases técnicas) requiere una segunda llamada por código. Esta sesión implementa esa segunda llamada como tarea Celery con auto-encolado desde el listado.

**Decisión arquitectónica ya tomada:** el trigger es **Opción A — auto-encolar desde `sync_listado_diario`**. Cuando la tarea de listado crea o actualiza una licitación, encola inmediatamente `sync_detalle_licitacion.delay(codigo)`. No bloquea; el detalle se procesa en background.

---

## Lecturas obligatorias antes de tocar código

Leer en este orden:

1. `docs/spec.md` — épica de sincronización de detalle (Sprint 2).
2. `docs/roadmap.md` — prioridades Sprint 2 y criterios de cierre.
3. `CLAUDE.md` — secciones 5 (reglas de oro #15, #18, #19, #21, #29), 9 (estados, cuota, formato fecha).
4. `docs/architecture.md` — ADR-003 (backfill API por fecha, distribución de cuota).
5. `backend/app/tasks/sync_chilecompra.py` — patrón de tarea Celery a replicar: `asyncio.run(_run())`, stats, idempotencia con hash, structlog.
6. `backend/app/services/chilecompra/client.py` líneas ~343–372 — método `obtener_detalle_licitacion` ya existente.
7. `backend/app/models/licitacion.py` — modelos `Licitacion`, `LicitacionItem`, `CriterioEvaluacion`, `LicitacionFecha`.
8. `backend/app/schemas/licitacion.py` — DTOs Pydantic disponibles.
9. `backend/app/celery_app.py` — registro de tareas en `include`.
10. `backend/app/tests/integration/test_sync_chilecompra.py` — patrón de tests con `respx` + `pytest-asyncio`.
11. `schema.sql` — índices únicos en `licitacion_items`, `criterios_evaluacion`, `licitacion_fechas` (necesario para upsert idempotente).

---

## Lo que ya está implementado (NO duplicar)

| Componente | Estado | Ubicación |
|---|---|---|
| Modelo `Licitacion` con `raw_payload`, `hash_contenido`, `detalle_sincronizado_at` | ✅ | `app/models/licitacion.py` |
| Modelos `LicitacionItem`, `CriterioEvaluacion`, `LicitacionFecha` con cascadas | ✅ | `app/models/licitacion.py` |
| `obtener_detalle_licitacion(codigo, ticket, ticket_id, empresa_id)` → `LicitacionDetalleResponseAPI` | ✅ | `app/services/chilecompra/client.py:~343` |
| Manejo de 404 con `LicitacionNoEncontradaError` | ✅ | `app/services/chilecompra/exceptions.py` |
| Schemas Pydantic para detalle, items, fechas | ✅ | `app/schemas/licitacion.py` |
| Tarea `sync_listado_diario` con patrón stats + structlog | ✅ | `app/tasks/sync_chilecompra.py` |
| Rate limiting 5 req/s + backoff exponencial | ✅ | Dentro del cliente HTTP |

---

## Tareas en orden

### TAREA 1 — Decisiones de diseño (sin código, ~15 min)

Revisar el código y resolver estas tres preguntas antes de escribir una sola línea:

1. **¿Dónde vive la nueva tarea?**
   - Opción A: agregarla en `app/tasks/sync_chilecompra.py` junto a `sync_listado_diario`.
   - Opción B: crear `app/tasks/sync_detalle.py` separado.
   - Criterio: seguir el patrón que ya existe en el repo. Si hay una sola tarea por archivo → separar. Si hay precedente de múltiples → agrupar.

2. **¿Cuándo se re-sincroniza el detalle?**
   - Si `detalle_sincronizado_at` ya está poblado y el `hash_contenido` del listado no cambió → retornar `sin_cambio` sin llamar a la API (regla de oro #21 — cache agresivo).
   - Si el hash cambió (estado nuevo) → re-sincronizar.

3. **¿Qué hacer ante 404?**
   - Licitación puede haber sido revocada o eliminada en ChileCompra.
   - Opción: loguear `no_encontrada=1`, dejar `detalle_sincronizado_at` nulo, no elevar excepción.
   - Si hay un campo para marcar "licitación inválida" en el modelo → usarlo.

Documentar las tres decisiones en un docstring de bloque al inicio del archivo de la tarea. No es un ADR completo — 5-10 líneas alcanzan.

### TAREA 2 — Implementación de `sync_detalle_licitacion`

Crear la tarea con esta estructura base (adaptar según decisiones TAREA 1):

```python
@celery_app.task(
    bind=True,
    autoretry_for=(MercadoPublicoError,),
    retry_backoff=True,
    max_retries=3,
)
def sync_detalle_licitacion(self, codigo: str) -> dict[str, int]:
    return asyncio.run(_run(codigo))
```

La función `_run(codigo)` debe:
1. Obtener ticket activo (replicar `_get_ticket_activo` de `backfill.py` o factorizar a util en `app/services/chilecompra/`).
2. Verificar si ya está sincronizado y el hash no cambió → retornar `sin_cambio` temprano.
3. Llamar `obtener_detalle_licitacion(codigo, ticket, ticket_id, empresa_id)`.
4. Persistir en una sola transacción:
   - `Licitacion.raw_payload`, `hash_contenido` (del detalle completo), `detalle_sincronizado_at = now(UTC)`.
   - `LicitacionItem`: upsert por índice único — verificar en `schema.sql` cuál es (probablemente `(licitacion_codigo, numero_item)`).
   - `CriterioEvaluacion`: upsert por índice único.
   - `LicitacionFecha`: upsert por índice único.
5. Retornar stats `{'nueva': 0, 'actualizada': 0, 'sin_cambio': 0, 'no_encontrada': 0, 'error': 0}`.

**Loguear con structlog:** keys `codigo`, resultado, tiempo de ejecución. Sin PII (regla #12). Sin loguear el ticket (regla #2).

### TAREA 3 — Modificar `sync_listado_diario`

En `backend/app/tasks/sync_chilecompra.py`, tras cada licitación con resultado `'nueva'` o `'actualizada'`:

```python
sync_detalle_licitacion.delay(codigo)
```

- Solo encolar en `nueva` y `actualizada`. **No** en `sin_cambio`.
- No bloquear: `.delay()`, no `.apply_async().get()`.
- Importar la tarea al inicio del archivo para evitar importación circular (o usar string task name si hay circularidad).

### TAREA 4 — Registro en Celery

Si la nueva tarea está en un archivo separado, agregar al `include` en `backend/app/celery_app.py`:

```python
include=[
    "app.tasks.sync_chilecompra",
    "app.tasks.sync_detalle",  # ← nuevo
]
```

Si está en el mismo archivo → no hay cambio en `celery_app.py`.

### TAREA 5 — Tests

Crear `backend/app/tests/integration/test_sync_detalle_licitacion.py` replicando el patrón de `test_sync_chilecompra.py`:

**`test_sync_detalle_licitacion_nueva`**
- Mock de `obtener_detalle_licitacion` retorna detalle completo con items/criterios/fechas.
- Ejecutar la tarea.
- Verificar: `detalle_sincronizado_at` no nulo, `raw_payload` poblado, N items en BD, M criterios, K fechas.

**`test_sync_detalle_licitacion_idempotente`**
- Ejecutar la tarea dos veces con el mismo mock.
- Segunda corrida debe retornar `sin_cambio = 1`, sin duplicar filas en `licitacion_items`.

**`test_sync_detalle_licitacion_404`**
- Mock lanza `LicitacionNoEncontradaError`.
- Tarea retorna `no_encontrada=1`, no eleva, `detalle_sincronizado_at` sigue nulo.

**`test_sync_listado_encola_detalle`**
- Mock del listado retorna 2 licitaciones nuevas + 1 sin cambio.
- Verificar que `sync_detalle_licitacion.delay` fue llamada exactamente 2 veces (monkeypatch del `.delay`).

Cobertura mínima: **70% en `services/` y `tasks/`** (`CLAUDE.md` sección 7).

### TAREA 6 — Documentación operacional

Agregar sección en `docs/runbook.md`:

```markdown
## Tarea `sync_detalle_licitacion`

**Disparo:** auto-encolada por `sync_listado_diario` para cada licitación nueva o modificada.
**Cuota:** ~1 req/licitación-nueva. En días normales: 20-200 req dependiendo del volumen publicado.
**Monitorear:** Flower en `localhost:5555`, filtrar por task name. structlog keys: `codigo`, `resultado`, `duracion_ms`.
**Reprocesar manualmente:**
    docker compose exec api python -c "
    from app.tasks.sync_detalle import sync_detalle_licitacion
    sync_detalle_licitacion.delay('1234567-8-L126').get(timeout=30)
    "
**Ante 404 masivo:** ChileCompra puede estar en mantenimiento. Revisar status en mercadopublico.cl.
```

Si la implementación generó decisiones relevantes no triviales (política 404, estructura de upsert), agregar **ADR-004** corto en `docs/architecture.md`.

---

## Restricciones (reglas de oro aplicables)

| # | Regla | Impacto en esta tarea |
|---|---|---|
| #2 | Tickets siempre cifrados, descifrar solo en memoria | `_get_ticket_activo` → `decrypt_ticket` → usar en RAM, borrar referencia al final |
| #12 | Sin PII en logs | Solo `codigo` (clave natural de Mercado Público), stats; nunca nombre de la empresa |
| #18 | Máximo 5 req/s por ticket | Ya lo maneja el cliente HTTP; no implementar lógica paralela en la tarea |
| #19 | Sin queries N+1 | Si necesitás leer items existentes para comparar → usar `selectinload` o query en batch |
| #21 | Cache agresivo de detalles | Si `detalle_sincronizado_at` no es nulo y hash no cambió → retornar `sin_cambio` sin API call |
| #22 | Toda IA pasa por capa de abstracción | No aplica en esta tarea |
| #29 | Tareas Celery idempotentes | Upsert en items/criterios/fechas; re-ejecutar no duplica filas |

---

## Verificación end-to-end

```bash
# 1. Tests
docker compose exec api pytest tests/integration/test_sync_detalle_licitacion.py -v
docker compose exec api pytest tests/integration/test_sync_chilecompra.py -v  # asegurarse que no rompimos el listado
docker compose exec api pytest --cov=app/services --cov=app/tasks --cov-report=term-missing

# 2. Lint y type check
docker compose exec api ruff check --fix && docker compose exec api ruff format
docker compose exec api mypy app

# 3. Ciclo manual (con ticket activo en BD — ver CLAUDE.md sección 6)
docker compose exec api python -c "
from app.tasks.sync_chilecompra import sync_listado_diario
result = sync_listado_diario.delay().get(timeout=120)
print(result)
"
# Esperar 2-3 min y verificar en BD:
docker compose exec postgres psql -U radar -d radar -c "
select
  count(*) filter (where detalle_sincronizado_at is not null) as con_detalle,
  count(*) as total_licitaciones
from licitaciones;
"
docker compose exec postgres psql -U radar -d radar -c "
select count(*) as items from licitacion_items;
select count(*) as criterios from criterios_evaluacion;
select count(*) as fechas from licitacion_fechas;
"

# 4. Cuota (columna correcta es created_at, no creado_en — inconsistencia conocida)
docker compose exec postgres psql -U radar -d radar -c "
select endpoint, count(*) as requests
from api_quota_log
where created_at > now() - interval '1 hour'
group by endpoint order by requests desc;
"
```

---

## Commits esperados

```
feat(sync): tarea sync_detalle_licitacion con upsert idempotente
feat(sync): auto-encolado de detalle desde sync_listado_diario
test(sync): cobertura sync_detalle (nueva, idempotente, 404, encolado)
docs(runbook): operación de sync_detalle_licitacion
docs(architecture): ADR-004 política de sincronización de detalle   ← solo si aplica
```

Formato: Conventional Commits en español. Sin `Co-Authored-By`.

---

## Cierre de sesión (obligatorio)

Antes de terminar, ejecutar:

```python
# Para cada decisión arquitectónica tomada:
mem_save(
    title="...",
    type="decision",  # o "architecture"
    project="radar-publico",
    topic_key="architecture/sync-detalle-...",
    content="What: ...\nWhy: ...\nWhere: ...\nLearned: ..."
)

# Al final:
mem_session_summary(
    project="radar-publico",
    content="""
## Goal
Implementar sync_detalle_licitacion con auto-encolado desde sync_listado_diario.

## Discoveries
- [lo que encontraste que no era obvio]

## Accomplished
- [lista de lo completado]

## Next Steps
- [lo que queda para la siguiente sesión]

## Relevant Files
- backend/app/tasks/... — [descripción]
"""
)
```
