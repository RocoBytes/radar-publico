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
