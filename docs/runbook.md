# Runbook — Radar Público

Procedimientos operacionales para incidentes y mantenimiento.

---

## Tarea `sync_listado_diario`

**Disparo:** Celery Beat cada 15 minutos (configurable en `celery_app.py`).  
**Cuota:** 1 request por empresa activa por ejecución. Con 1 empresa: 1 req/15 min = ~96 req/día.  
**Monitorear:** Flower en `localhost:5555`, filtrar por `tasks.sync_chilecompra.sync_listado_diario`. structlog keys: `empresas`, `nuevas`, `actualizadas`, `sin_cambio`, `errores`.  
**Reprocesar manualmente:**
```bash
docker compose exec api python -c "
from app.tasks.sync_chilecompra import sync_listado_diario
result = sync_listado_diario.delay().get(timeout=120)
print(result)
"
```

---

## Tarea `sync_detalle_licitacion`

**Disparo:** Auto-encolada por `sync_listado_diario` para cada licitación nueva o con hash modificado.  
**Cuota:** ~1 req/licitación-nueva. En días normales: 20–200 req adicionales dependiendo del volumen publicado por ChileCompra.  
**Monitorear:** Flower en `localhost:5555`, filtrar por `tasks.sync_detalle.sync_detalle_licitacion`. structlog keys: `codigo`, `resultado` (nueva/actualizada/sin_cambio), `duracion_ms`.  
**Reprocesar manualmente:**
```bash
docker compose exec api python -c "
from app.tasks.sync_detalle import sync_detalle_licitacion
result = sync_detalle_licitacion.delay('1234567-8-L126').get(timeout=30)
print(result)
"
```
**Reprocesar lote (licitaciones sin detalle):**
```bash
docker compose exec api python -c "
from sqlalchemy import select
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.licitacion import Licitacion
from app.tasks.sync_detalle import sync_detalle_licitacion

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Licitacion.codigo).where(
                Licitacion.detalle_sincronizado_at.is_(None)
            ).limit(100)
        )
        codigos = [row[0] for row in result.all()]
    for codigo in codigos:
        sync_detalle_licitacion.delay(codigo)
    print(f'{len(codigos)} tareas encoladas')

asyncio.run(main())
"
```
**Ante 404 masivo:** ChileCompra puede estar en mantenimiento. Revisar status en `mercadopublico.cl`. La tarea logueará `sync_detalle_no_encontrada` con el `codigo` — no reintenta en 404 (política de diseño: 404 es semántico, no transitorio).  
**Ante errores 5xx o rate limit:** Celery reintenta automáticamente hasta 3 veces con backoff exponencial. Si persiste, revisar `MercadoPublicoError` en los logs de Flower y esperar ventana de recuperación.

---

## Verificar consumo de cuota

```bash
# Columna correcta es created_at (inconsistencia conocida con creado_en en schema)
docker compose exec postgres psql -U radar -d radar -c "
SELECT endpoint, COUNT(*) AS requests
FROM api_quota_log
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY endpoint
ORDER BY requests DESC;
"
```

---

## Verificar estado de sincronización

```bash
docker compose exec postgres psql -U radar -d radar -c "
SELECT
  COUNT(*) FILTER (WHERE detalle_sincronizado_at IS NOT NULL) AS con_detalle,
  COUNT(*) FILTER (WHERE detalle_sincronizado_at IS NULL) AS sin_detalle,
  COUNT(*) AS total_licitaciones
FROM licitaciones;
"

docker compose exec postgres psql -U radar -d radar -c "
SELECT COUNT(*) AS items FROM licitacion_items;
SELECT COUNT(*) AS criterios FROM criterios_evaluacion;
SELECT COUNT(*) AS fechas FROM licitacion_fechas;
"
```

---

## Scraper de bases (worker_scraper)

### Monitorear estado del worker

```bash
# Logs del worker (seguir en tiempo real)
docker compose logs -f worker_scraper

# Estado del queue 'scraping' en Flower
# Abrir http://localhost:5555 → queues → scraping

# Ver tareas activas
docker compose exec redis redis-cli -n 1 llen celery
```

### Ver estado de descarga de bases

```bash
docker compose exec postgres psql -U radar -d radar -c "
SELECT
  COUNT(*) FILTER (WHERE bases_descargadas_at IS NOT NULL) AS con_bases,
  COUNT(*) FILTER (WHERE bases_descargadas_at IS NULL AND detalle_sincronizado_at IS NOT NULL) AS pendientes,
  COUNT(*) FILTER (WHERE bases_descargadas_at IS NULL AND detalle_sincronizado_at IS NULL) AS sin_detalle
FROM licitaciones;
"

docker compose exec postgres psql -U radar -d radar -c "
SELECT status, COUNT(*) FROM documentos_bases GROUP BY status ORDER BY status;
"
```

### Re-encolar manualmente una licitación

```bash
docker compose exec api python -c "
from app.celery_app import celery_app
celery_app.send_task('tasks.scrape_bases.scrape_bases_licitacion', args=['1234-56-LR26'], queue='scraping')
print('Encolado OK')
"
```

### Re-encolar todas las licitaciones sin bases (batch)

```bash
# Con cuidado: encola TODAS las pendientes. Correr en ventana nocturna.
docker compose exec api python -c "
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.licitacion import Licitacion
from app.celery_app import celery_app

async def main():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Licitacion.codigo).where(
                Licitacion.detalle_sincronizado_at.is_not(None),
                Licitacion.bases_descargadas_at.is_(None),
            ).limit(500)
        )
        codigos = [r[0] for r in result.all()]
    for codigo in codigos:
        celery_app.send_task('tasks.scrape_bases.scrape_bases_licitacion', args=[codigo], queue='scraping')
    print(f'Encoladas {len(codigos)} licitaciones')

asyncio.run(main())
"
```

### Ante PortalBloqueadoError masivo

**Síntomas:** múltiples logs `scrape_bases_portal_bloqueado` en poco tiempo, `status=error` en `documentos_bases`.

**Pasos:**

1. Pausar la queue para no quemar reintentos:
   ```bash
   docker compose exec redis redis-cli -n 1 client kill ID <worker_id>
   # O parar el worker directamente:
   docker compose stop worker_scraper
   ```

2. Verificar cuántas licitaciones afectadas:
   ```sql
   SELECT COUNT(*) FROM documentos_bases WHERE status = 'error' AND error_mensaje LIKE '%bloqueado%';
   ```

3. Esperar mínimo 24 horas antes de reintentar (posible bloqueo por IP temporal).

4. Si el bloqueo persiste, revisar si Mercado Público cambió su estructura de seguridad y contactar a soporte de ChileCompra.

5. Reiniciar el worker y limpiar errores para re-intentar:
   ```sql
   UPDATE documentos_bases SET status = 'pendiente', error_mensaje = NULL
   WHERE status = 'error' AND error_mensaje LIKE '%bloqueado%';
   ```
   Luego re-encolar con el batch script de arriba.

### Limpiar documentos huérfanos en R2

Si se eliminaron filas en `documentos_bases` manualmente (error de operación), los archivos en R2 pueden quedar huérfanos:

```bash
# Listar archivos en R2
aws s3 ls s3://radar-publico-dev/bases/ --recursive --endpoint-url=$R2_ENDPOINT | wc -l

# Comparar con filas en BD
docker compose exec postgres psql -U radar -d radar -c "SELECT COUNT(*) FROM documentos_bases WHERE storage_path IS NOT NULL;"

# Si hay discrepancia grande, contactar a Rodrigo antes de borrar en R2.
```
