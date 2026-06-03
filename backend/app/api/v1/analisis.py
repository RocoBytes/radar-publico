"""Endpoints REST para análisis IA de bases técnicas.

GET  /api/v1/licitaciones/{codigo}/analisis  — resultado del análisis (404 si no existe)
POST /api/v1/licitaciones/{codigo}/analisis  — encola o re-encola el análisis
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
import structlog

from app.api.deps import CurrentUser, DbDep, EmpresaDep  # noqa: TCH001
from app.models.analisis_ia import AnalisisBases, BorradorPropuesta
from app.models.documento_base import DocumentoChunk
from app.models.enums import AnalisisStatus
from app.models.licitacion import Licitacion
from app.schemas.inteligencia import InadmisibilidadResponse, ItemAdmisibilidad, NivelRiesgo
from app.schemas.licitaciones import AnalisisBasesResponse, BorradorPropuestaResponse

router = APIRouter(prefix="/licitaciones", tags=["analisis-ia"])
logger = structlog.get_logger()


@router.get(
    "/{codigo}/analisis",
    response_model=AnalisisBasesResponse,
    summary="Resultado del análisis IA de las bases técnicas",
)
async def get_analisis_bases(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> AnalisisBasesResponse:
    """Retorna el análisis IA más reciente de las bases técnicas de una licitación.

    404 si la licitación no existe o si todavía no hay análisis disponible.
    Cuando status='pendiente' o 'procesando', el cliente debe re-consultar en ~5s.
    """
    result = await db.execute(
        select(AnalisisBases).where(
            AnalisisBases.licitacion_codigo == codigo,
            AnalisisBases.version == 1,
        )
    )
    analisis: AnalisisBases | None = result.scalar_one_or_none()

    if analisis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Análisis no disponible. Usá POST para solicitarlo.",
        )

    return AnalisisBasesResponse.model_validate(analisis)


@router.post(
    "/{codigo}/analisis",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Solicitar análisis IA de las bases técnicas",
)
async def trigger_analisis_bases(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> dict[str, str]:
    """Encola el análisis IA de las bases técnicas de una licitación.

    - 202 si la tarea fue encolada (o ya estaba en proceso/lista).
    - 404 si la licitación no existe.
    - 422 si las bases aún no fueron procesadas (sin chunks disponibles).
    """
    lic: Licitacion | None = await db.get(Licitacion, codigo)
    if lic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada.",
        )

    # Verificar que haya chunks (bases procesadas)
    chunks_count = (
        await db.execute(
            select(DocumentoChunk.id)
            .where(
                DocumentoChunk.licitacion_codigo == codigo,
                DocumentoChunk.embedding.isnot(None),
            )
            .limit(1)
        )
    ).first()

    if chunks_count is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Las bases de esta licitación aún no fueron procesadas. "
                "El análisis estará disponible una vez que se descarguen y procesen los PDFs."
            ),
        )

    # Verificar estado actual del análisis
    result = await db.execute(
        select(AnalisisBases).where(
            AnalisisBases.licitacion_codigo == codigo,
            AnalisisBases.version == 1,
        )
    )
    analisis: AnalisisBases | None = result.scalar_one_or_none()

    if analisis and analisis.status == AnalisisStatus.procesando:
        return {"status": "en_proceso", "mensaje": "El análisis ya está en proceso."}

    if analisis and analisis.status == AnalisisStatus.listo:
        return {"status": "listo", "mensaje": "El análisis ya está disponible. Usá GET para verlo."}

    # Encolar tarea (idempotente — la tarea verifica el estado antes de procesar)
    from app.celery_app import celery_app

    celery_app.send_task(
        "tasks.analizar_bases.analizar_bases_licitacion",
        args=[codigo],
    )

    logger.info("analisis_encolado", codigo=codigo)
    return {
        "status": "encolado",
        "mensaje": "El análisis fue solicitado. Consultá el resultado en unos segundos.",
    }


# ── Módulo 1b: Inadmisibilidad derivada del análisis de bases ────────────────


def _computar_nivel_riesgo(
    n_restricciones: int,
    n_documentos: int,
    n_requisitos: int,
) -> NivelRiesgo:
    """Clasifica el riesgo de inadmisibilidad según cantidad de ítems críticos.

    Lógica conservadora: las restricciones son el factor de mayor peso porque
    una sola puede desclasificar la oferta completa.
    """
    if n_restricciones >= 3 or (n_restricciones >= 1 and n_documentos >= 3):
        return "alto"
    if n_restricciones >= 1 or n_documentos >= 3 or n_requisitos >= 4:
        return "medio"
    return "bajo"


def _resumen_riesgo(nivel: NivelRiesgo, n_items: int) -> str:
    textos: dict[NivelRiesgo, str] = {
        "alto": (
            f"Se detectaron {n_items} factores formales de riesgo alto. "
            "Revisá cada restricción con atención antes de decidir postular."
        ),
        "medio": (
            f"Hay {n_items} requisito{'s' if n_items != 1 else ''}"
            f" formal{'es' if n_items != 1 else ''} "
            "que debés verificar. El riesgo es manejable si reunís la documentación a tiempo."
        ),
        "bajo": (
            "Perfil de admisibilidad favorable. "
            "Solo {n_items} requisito{'s' if n_items != 1 else ''}"
            " formal{'es' if n_items != 1 else ''} estándar."
            if n_items > 0
            else "No se detectaron barreras formales de admisibilidad en las bases."
        ),
    }
    return textos[nivel]


@router.get(
    "/{codigo}/inadmisibilidad",
    response_model=InadmisibilidadResponse,
    summary="Evaluación de riesgo de inadmisibilidad basada en el análisis de bases",
)
async def get_inadmisibilidad(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
) -> InadmisibilidadResponse:
    """Retorna el riesgo de inadmisibilidad derivado del análisis IA de las bases.

    Computa los ítems a partir de restricciones, documentos_obligatorios y
    requisitos_tecnicos del AnalisisBases. No realiza llamada LLM adicional.

    - 200 con analisis_disponible=False si no hay análisis listo (sin 404).
    - 404 si la licitación no existe.
    """
    lic: Licitacion | None = await db.get(Licitacion, codigo)
    if lic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada.",
        )

    result = await db.execute(
        select(AnalisisBases).where(
            AnalisisBases.licitacion_codigo == codigo,
            AnalisisBases.version == 1,
            AnalisisBases.status == AnalisisStatus.listo,
        )
    )
    analisis: AnalisisBases | None = result.scalar_one_or_none()

    if analisis is None:
        return InadmisibilidadResponse(
            analisis_disponible=False,
            nivel_riesgo=None,
            items=[],
            resumen=None,
        )

    items: list[ItemAdmisibilidad] = []

    for r in analisis.restricciones or []:
        descripcion = r if isinstance(r, str) else r.get("descripcion", str(r))
        items.append(
            ItemAdmisibilidad(tipo="restriccion", descripcion=descripcion, urgencia="alta")
        )

    for d in analisis.documentos_obligatorios or []:
        if isinstance(d, dict):
            nombre = d.get("nombre", "")
            desc = d.get("descripcion", "")
            texto = f"{nombre}: {desc}".strip(": ") if nombre else desc
        else:
            texto = str(d)
        if texto:
            items.append(ItemAdmisibilidad(tipo="documento", descripcion=texto, urgencia="media"))

    for req in analisis.requisitos_tecnicos or []:
        if isinstance(req, dict) and req.get("tipo") == "obligatorio":
            descripcion = req.get("descripcion", str(req))
            items.append(
                ItemAdmisibilidad(tipo="requisito", descripcion=descripcion, urgencia="media")
            )

    n_restricciones = sum(1 for i in items if i.tipo == "restriccion")
    n_documentos = sum(1 for i in items if i.tipo == "documento")
    n_requisitos = sum(1 for i in items if i.tipo == "requisito")

    nivel = _computar_nivel_riesgo(n_restricciones, n_documentos, n_requisitos)

    return InadmisibilidadResponse(
        analisis_disponible=True,
        nivel_riesgo=nivel,
        items=items,
        resumen=_resumen_riesgo(nivel, len(items)),
    )


# ── Módulo 2: Borrador de propuesta técnica ───────────────────────────────────


@router.get(
    "/{codigo}/propuesta",
    response_model=BorradorPropuestaResponse,
    summary="Borrador de propuesta técnica personalizado",
)
async def get_borrador_propuesta(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
    empresa: EmpresaDep,
) -> BorradorPropuestaResponse:
    """Retorna el borrador de propuesta técnica más reciente para la empresa.

    404 si la licitación no existe o si todavía no hay borrador disponible.
    Cuando status='pendiente' o 'procesando', el cliente debe re-consultar en ~5s.
    """
    result = await db.execute(
        select(BorradorPropuesta).where(
            BorradorPropuesta.licitacion_codigo == codigo,
            BorradorPropuesta.empresa_id == empresa.id,
            BorradorPropuesta.version == 1,
        )
    )
    borrador: BorradorPropuesta | None = result.scalar_one_or_none()

    if borrador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrador no disponible. Usá POST para generarlo.",
        )

    return BorradorPropuestaResponse.model_validate(borrador)


@router.post(
    "/{codigo}/propuesta",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generar borrador de propuesta técnica",
)
async def trigger_borrador_propuesta(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
    empresa: EmpresaDep,
) -> dict[str, str]:
    """Encola la generación del borrador de propuesta técnica personalizado.

    - 202 si la tarea fue encolada (o ya estaba en proceso/lista).
    - 404 si la licitación no existe o si el análisis de bases no está listo.
    - 422 si las bases aún no fueron analizadas (análisis IA pendiente).
    """
    lic: Licitacion | None = await db.get(Licitacion, codigo)
    if lic is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Licitación '{codigo}' no encontrada.",
        )

    # El análisis de bases debe estar listo (es la entrada del borrador)
    analisis_result = await db.execute(
        select(AnalisisBases).where(
            AnalisisBases.licitacion_codigo == codigo,
            AnalisisBases.version == 1,
            AnalisisBases.status == AnalisisStatus.listo,
        )
    )
    if analisis_result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "El análisis de bases aún no está disponible. "
                "Solicitá primero el análisis IA de las bases técnicas."
            ),
        )

    # Verificar estado actual del borrador
    borrador_result = await db.execute(
        select(BorradorPropuesta).where(
            BorradorPropuesta.licitacion_codigo == codigo,
            BorradorPropuesta.empresa_id == empresa.id,
            BorradorPropuesta.version == 1,
        )
    )
    borrador: BorradorPropuesta | None = borrador_result.scalar_one_or_none()

    if borrador and borrador.status == AnalisisStatus.procesando:
        return {"status": "en_proceso", "mensaje": "El borrador ya se está generando."}

    if borrador and borrador.status == AnalisisStatus.listo:
        return {"status": "listo", "mensaje": "El borrador ya está disponible. Usá GET para verlo."}

    # Encolar tarea (idempotente — la tarea verifica el estado antes de procesar)
    from app.celery_app import celery_app

    celery_app.send_task(
        "tasks.generar_borrador.generar_borrador_propuesta",
        args=[codigo, str(empresa.id)],
    )

    logger.info("borrador_encolado", codigo=codigo, empresa_id=str(empresa.id))
    return {
        "status": "encolado",
        "mensaje": "El borrador fue solicitado. Consultá el resultado en unos segundos.",
    }


@router.get(
    "/{codigo}/propuesta/export",
    summary="Exportar borrador de propuesta técnica como DOCX",
    response_class=StreamingResponse,
)
async def export_borrador_propuesta_docx(
    codigo: str,
    db: DbDep,
    _current_user: CurrentUser,
    empresa: EmpresaDep,
) -> StreamingResponse:
    """Descarga el borrador de propuesta técnica en formato DOCX.

    404 si no hay borrador disponible o no está en status='listo'.
    """
    from app.services.docx_export import generar_docx_borrador

    result = await db.execute(
        select(BorradorPropuesta).where(
            BorradorPropuesta.licitacion_codigo == codigo,
            BorradorPropuesta.empresa_id == empresa.id,
            BorradorPropuesta.version == 1,
            BorradorPropuesta.status == AnalisisStatus.listo,
        )
    )
    borrador: BorradorPropuesta | None = result.scalar_one_or_none()

    if borrador is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay borrador listo para exportar. Generá el borrador primero.",
        )

    buffer = generar_docx_borrador(borrador)
    filename = f"propuesta-{codigo}.docx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
