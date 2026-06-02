"""Servicio de checklist documental para ítems del pipeline.

Todas las funciones son async y verifican que el pipeline_item
pertenezca a la empresa solicitante antes de operar (403/404).
"""

from datetime import UTC, datetime
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analisis_ia import AnalisisBases
from app.models.enums import AnalisisStatus, ChecklistItemEstado, ChecklistItemOrigen
from app.models.eventos_auditoria import EventoAuditoria
from app.models.pipeline import PipelineChecklistItem, PipelineItem
from app.schemas.checklist import (
    ChecklistBootstrapResponse,
    ChecklistItemCreate,
    ChecklistItemResponse,
    ChecklistItemUpdate,
)


async def _get_pipeline_item_de_empresa(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    empresa_id: uuid.UUID,
) -> PipelineItem:
    """Recupera un pipeline_item verificando que pertenezca a la empresa.

    Raises:
        HTTPException 404: pipeline_item no existe.
        HTTPException 403: el ítem existe pero pertenece a otra empresa.
    """
    result = await db.execute(
        select(PipelineItem).where(PipelineItem.id == pipeline_item_id)
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline item '{pipeline_item_id}' no encontrado",
        )
    if item.empresa_id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenés permiso para acceder a este ítem del pipeline",
        )
    return item


async def get_items(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    empresa_id: uuid.UUID,
) -> list[PipelineChecklistItem]:
    """Retorna los ítems del checklist de un pipeline_item, ordenados por orden ASC.

    Verifica ownership antes de retornar.
    """
    await _get_pipeline_item_de_empresa(db, pipeline_item_id, empresa_id)

    result = await db.execute(
        select(PipelineChecklistItem)
        .where(PipelineChecklistItem.pipeline_item_id == pipeline_item_id)
        .order_by(PipelineChecklistItem.orden.asc(), PipelineChecklistItem.created_at.asc())
    )
    return list(result.scalars().all())


async def create_item(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    empresa_id: uuid.UUID,
    data: ChecklistItemCreate,
) -> PipelineChecklistItem:
    """Crea un ítem manual en el checklist del pipeline_item.

    El origen queda forzado a ChecklistItemOrigen.manual.
    """
    await _get_pipeline_item_de_empresa(db, pipeline_item_id, empresa_id)

    now = datetime.now(UTC)
    item = PipelineChecklistItem(
        pipeline_item_id=pipeline_item_id,
        nombre=data.nombre,
        descripcion=data.descripcion,
        obligatorio=data.obligatorio,
        orden=data.orden,
        origen=ChecklistItemOrigen.manual,
        estado=ChecklistItemEstado.pendiente,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


async def update_item(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    item_id: uuid.UUID,
    empresa_id: uuid.UUID,
    data: ChecklistItemUpdate,
) -> PipelineChecklistItem:
    """Actualiza parcialmente un ítem del checklist.

    Si estado cambia a 'completado' y completed_at es None, setea now().
    Si estado sale de 'completado', limpia completed_at.
    """
    await _get_pipeline_item_de_empresa(db, pipeline_item_id, empresa_id)

    result = await db.execute(
        select(PipelineChecklistItem).where(
            PipelineChecklistItem.id == item_id,
            PipelineChecklistItem.pipeline_item_id == pipeline_item_id,
        )
    )
    checklist_item = result.scalar_one_or_none()
    if checklist_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ítem de checklist '{item_id}' no encontrado",
        )

    # Aplicar solo los campos presentes en el payload (semantica PATCH)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field != "estado":
            setattr(checklist_item, field, value)

    # Lógica especial para completed_at
    if "estado" in update_data:
        nuevo_estado = update_data["estado"]
        checklist_item.estado = nuevo_estado
        if nuevo_estado == ChecklistItemEstado.completado and checklist_item.completed_at is None:
            checklist_item.completed_at = datetime.now(UTC)
        elif nuevo_estado != ChecklistItemEstado.completado:
            checklist_item.completed_at = None

    checklist_item.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(checklist_item)
    return checklist_item


async def delete_item(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    item_id: uuid.UUID,
    empresa_id: uuid.UUID,
) -> None:
    """Elimina un ítem del checklist. Registra auditoría en eventos_auditoria."""
    await _get_pipeline_item_de_empresa(db, pipeline_item_id, empresa_id)

    result = await db.execute(
        select(PipelineChecklistItem).where(
            PipelineChecklistItem.id == item_id,
            PipelineChecklistItem.pipeline_item_id == pipeline_item_id,
        )
    )
    checklist_item = result.scalar_one_or_none()
    if checklist_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ítem de checklist '{item_id}' no encontrado",
        )

    await db.delete(checklist_item)

    audit = EventoAuditoria(
        empresa_id=empresa_id,
        accion="pipeline.checklist.item.eliminado",
        recurso_tipo="pipeline_checklist_item",
        recurso_id=str(item_id),
    )
    db.add(audit)
    await db.commit()


async def bootstrap_from_analysis(
    db: AsyncSession,
    pipeline_item_id: uuid.UUID,
    empresa_id: uuid.UUID,
) -> ChecklistBootstrapResponse:
    """Inicializa el checklist desde el análisis IA de la licitación.

    Busca el AnalisisBases más reciente con status='listo' para el
    licitacion_codigo del pipeline_item. Si no existe, retorna lista vacía
    sin error.

    El INSERT usa ON CONFLICT DO NOTHING sobre el índice único parcial
    uq_checklist_ia_dedup (pipeline_item_id, lower(nombre)) WHERE origen='ia_generado'.
    Esto garantiza idempotencia atómica — múltiples llamadas concurrentes no duplican.

    Registra auditoría en eventos_auditoria.
    """
    pipeline_item = await _get_pipeline_item_de_empresa(db, pipeline_item_id, empresa_id)

    # Buscar análisis más reciente listo para esta licitación
    analisis_result = await db.execute(
        select(AnalisisBases)
        .where(
            AnalisisBases.licitacion_codigo == pipeline_item.licitacion_codigo,
            AnalisisBases.status == AnalisisStatus.listo,
        )
        .order_by(AnalisisBases.version.desc())
        .limit(1)
    )
    analisis = analisis_result.scalar_one_or_none()

    if analisis is None or not analisis.documentos_obligatorios:
        # Sin análisis disponible o sin documentos — retornar vacío sin error
        items_result = await db.execute(
            select(PipelineChecklistItem)
            .where(PipelineChecklistItem.pipeline_item_id == pipeline_item_id)
            .order_by(PipelineChecklistItem.orden.asc(), PipelineChecklistItem.created_at.asc())
        )
        current_items = list(items_result.scalars().all())
        return ChecklistBootstrapResponse(
            creados=0,
            omitidos=0,
            items=[ChecklistItemResponse.model_validate(i) for i in current_items],
        )

    creados = 0
    omitidos = 0
    now = datetime.now(UTC)

    for doc in analisis.documentos_obligatorios:
        # doc es un dict con al menos 'nombre'; 'descripcion' y 'obligatorio' son opcionales
        nombre = doc.get("nombre", "") if isinstance(doc, dict) else str(doc)
        if not nombre:
            continue

        descripcion = doc.get("descripcion") if isinstance(doc, dict) else None
        obligatorio = bool(doc.get("obligatorio", False)) if isinstance(doc, dict) else False

        # INSERT atómico con ON CONFLICT DO NOTHING — la BD garantiza idempotencia
        # El índice uq_checklist_ia_dedup cubre (pipeline_item_id, lower(nombre))
        # WHERE origen = 'ia_generado'
        result = await db.execute(
            text(
                """
                INSERT INTO pipeline_checklist_items
                    (id, pipeline_item_id, nombre, descripcion, obligatorio,
                     estado, origen, orden, created_at, updated_at)
                VALUES
                    (uuid_generate_v4(), :pipeline_item_id, :nombre, :descripcion,
                     :obligatorio, 'pendiente', 'ia_generado', 0, :now, :now)
                ON CONFLICT (pipeline_item_id, lower(nombre))
                WHERE origen = 'ia_generado'
                DO NOTHING
                """
            ),
            {
                "pipeline_item_id": str(pipeline_item_id),
                "nombre": nombre,
                "descripcion": descripcion,
                "obligatorio": obligatorio,
                "now": now,
            },
        )
        rows_affected = result.rowcount
        if rows_affected > 0:
            creados += 1
        else:
            omitidos += 1

    # Auditoría del bootstrap
    audit = EventoAuditoria(
        empresa_id=empresa_id,
        accion="pipeline.checklist.bootstrap",
        recurso_tipo="pipeline_item",
        recurso_id=str(pipeline_item_id),
        info={"creados": creados, "omitidos": omitidos},
    )
    db.add(audit)
    await db.commit()

    # Retornar lista actualizada
    items_result = await db.execute(
        select(PipelineChecklistItem)
        .where(PipelineChecklistItem.pipeline_item_id == pipeline_item_id)
        .order_by(PipelineChecklistItem.orden.asc(), PipelineChecklistItem.created_at.asc())
    )
    current_items = list(items_result.scalars().all())

    return ChecklistBootstrapResponse(
        creados=creados,
        omitidos=omitidos,
        items=[ChecklistItemResponse.model_validate(i) for i in current_items],
    )
