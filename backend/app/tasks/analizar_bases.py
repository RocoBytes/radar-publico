"""Tarea Celery: análisis LLM de las bases técnicas de una licitación.

Decisiones de diseño:

1. IDEMPOTENCIA: si el análisis ya está en status='listo' o 'procesando',
   se salta sin error. Re-ejecutar cuando status='error' reinicia el análisis.

2. CONTENIDO: pasa todos los chunks de la licitación (cap en _MAX_CHUNKS)
   ordenados por posición en el documento. El contexto de Claude (200k tokens)
   soporta la mayoría de las bases técnicas chilenas.

3. SESIONES: la llamada al LLM ocurre fuera de cualquier sesión de BD para
   no mantener conexiones abiertas durante operaciones de red largas.

4. LOGGING: registra el uso en llm_usage_log (regla de oro #23).

5. TRIGGERED BY: marcar_licitacion_procesada al completar el pipeline PDF.
   También puede lanzarse manualmente desde un endpoint.

Reglas de oro que aplican:
- #22: Toda llamada al LLM pasa por services/llm/.
- #23: Logging de uso de IA en llm_usage_log.
- #29: Idempotente.
"""

import asyncio
from datetime import UTC, datetime
import json
from typing import Any

import structlog

from app.celery_app import celery_app
from app.services.llm.exceptions import LLMError, LLMRateLimitError

logger = structlog.get_logger()

_MAX_CHUNKS = 150  # ~120k tokens de contenido — dentro del contexto de Claude
_ANALISIS_VERSION = 1


async def _run(codigo: str) -> dict[str, Any]:
    """Lógica async: analiza las bases técnicas de una licitación con LLM."""
    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.analisis_ia import AnalisisBases
    from app.models.documento_base import DocumentoChunk
    from app.models.enums import AnalisisStatus
    from app.models.licitacion import CriterioEvaluacion, Licitacion
    from app.models.organismo import Organismo
    from app.services.llm.client import completion
    from app.services.llm.prompts import ANALISIS_BASES
    from app.services.llm.usage_log import registrar_uso

    stats: dict[str, Any] = {
        "licitacion_codigo": codigo,
        "status": "skip",
        "tokens_in": 0,
        "tokens_out": 0,
    }

    # ── Sesión 1: verificar idempotencia, cargar datos, marcar 'procesando' ──
    analisis_id: Any = None
    nombre_lic: str = ""
    nombre_org: str = "No disponible"
    criterios_lineas: list[str] = []
    chunks_texto: list[str] = []

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AnalisisBases).where(
                AnalisisBases.licitacion_codigo == codigo,
                AnalisisBases.version == _ANALISIS_VERSION,
            )
        )
        analisis: AnalisisBases | None = result.scalar_one_or_none()

        if analisis and analisis.status in (AnalisisStatus.listo, AnalisisStatus.procesando):
            stats["status"] = analisis.status.value
            logger.debug("analizar_bases_skip", codigo=codigo, status=analisis.status)
            return stats

        lic: Licitacion | None = await session.get(Licitacion, codigo)
        if lic is None:
            logger.warning("analizar_bases_licitacion_no_encontrada", codigo=codigo)
            stats["status"] = "licitacion_no_encontrada"
            return stats

        organismo: Organismo | None = (
            await session.get(Organismo, lic.codigo_organismo) if lic.codigo_organismo else None
        )

        criterios_result = await session.execute(
            select(CriterioEvaluacion)
            .where(CriterioEvaluacion.licitacion_codigo == codigo)
            .order_by(CriterioEvaluacion.orden)
        )
        criterios = list(criterios_result.scalars().all())

        chunks_result = await session.execute(
            select(DocumentoChunk)
            .where(
                DocumentoChunk.licitacion_codigo == codigo,
                DocumentoChunk.embedding.isnot(None),
            )
            .order_by(DocumentoChunk.chunk_orden)
            .limit(_MAX_CHUNKS)
        )
        chunks = list(chunks_result.scalars().all())

        if not chunks:
            logger.warning("analizar_bases_sin_chunks", codigo=codigo)
            stats["status"] = "sin_chunks"
            return stats

        # Extraer valores a Python puro antes de que el commit expire los objetos ORM
        nombre_lic = lic.nombre
        nombre_org = organismo.nombre if organismo else "No disponible"
        criterios_lineas = [
            f"- {c.nombre}: {float(c.ponderacion):.0f}%"
            + (f" — {c.descripcion}" if c.descripcion else "")
            for c in criterios
        ]
        chunks_texto = [c.contenido for c in chunks]

        # Crear o resetear el registro de análisis
        ahora = datetime.now(UTC)
        if analisis is None:
            analisis = AnalisisBases(
                licitacion_codigo=codigo,
                version=_ANALISIS_VERSION,
                status=AnalisisStatus.procesando,
                created_at=ahora,
                updated_at=ahora,
            )
            session.add(analisis)
        else:
            analisis.status = AnalisisStatus.procesando
            analisis.error_mensaje = None
            analisis.updated_at = ahora

        await session.flush()  # el DB asigna el UUID si es nuevo
        analisis_id = analisis.id
        await session.commit()

    # ── Llamada al LLM (fuera de sesión) ──────────────────────────────────────

    criterios_texto = (
        "\n".join(criterios_lineas) if criterios_lineas else "No hay criterios registrados."
    )
    contenido_bases = "\n\n---\n\n".join(chunks_texto)

    prompt_text = ANALISIS_BASES.render(
        codigo=codigo,
        nombre=nombre_lic,
        organismo=nombre_org,
        criterios=criterios_texto,
        contenido_bases=contenido_bases,
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt_text}]
    inicio = datetime.now(UTC)

    try:
        resultado = await completion(messages, temperature=0.1)
    except (LLMError, LLMRateLimitError) as exc:
        async with AsyncSessionLocal() as session:
            analisis_db: AnalisisBases | None = await session.get(AnalisisBases, analisis_id)
            if analisis_db:
                analisis_db.status = AnalisisStatus.error
                analisis_db.error_mensaje = str(exc)[:2000]
                analisis_db.updated_at = datetime.now(UTC)
                await session.commit()
        logger.error("analizar_bases_llm_error", codigo=codigo, error=str(exc))
        raise

    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)

    # ── Parsear JSON ───────────────────────────────────────────────────────────

    datos: dict[str, Any] = {}
    parse_error: str | None = None
    try:
        raw = resultado.content.strip()
        # Extraer bloque JSON si el modelo lo envuelve en markdown
        if raw.startswith("```"):
            partes = raw.split("```")
            raw = partes[1]
            if raw.startswith("json"):
                raw = raw[4:]
        datos = json.loads(raw)
    except json.JSONDecodeError as exc:
        parse_error = f"JSON inválido: {exc!s}"
        logger.error("analizar_bases_json_error", codigo=codigo, error=parse_error)

    # ── Sesión 2: persistir resultado ─────────────────────────────────────────

    async with AsyncSessionLocal() as session:
        analisis_db = await session.get(AnalisisBases, analisis_id)
        if analisis_db is None:
            logger.error("analizar_bases_registro_perdido", codigo=codigo)
            stats["status"] = "error_registro_perdido"
            return stats

        if parse_error:
            analisis_db.status = AnalisisStatus.error
            analisis_db.error_mensaje = parse_error
        else:
            analisis_db.status = AnalisisStatus.listo
            analisis_db.requisitos_tecnicos = datos.get("requisitos_tecnicos")
            analisis_db.criterios_extraidos = datos.get("criterios_extraidos")
            analisis_db.documentos_obligatorios = datos.get("documentos_obligatorios")
            analisis_db.plazos_clave = datos.get("plazos_clave")
            analisis_db.restricciones = datos.get("restricciones")
            analisis_db.resumen_ejecutivo = datos.get("resumen_ejecutivo")

        analisis_db.modelo_usado = resultado.modelo
        analisis_db.prompt_version = ANALISIS_BASES.version
        analisis_db.tokens_input = resultado.tokens_in
        analisis_db.tokens_output = resultado.tokens_out
        analisis_db.updated_at = datetime.now(UTC)

        final_status = analisis_db.status  # leer antes del commit

        await registrar_uso(
            session,
            provider="anthropic",
            modelo=resultado.modelo,
            tokens_in=resultado.tokens_in,
            tokens_out=resultado.tokens_out,
            feature="analizar_bases_licitacion",
            duracion_ms=duracion_ms,
        )
        await session.commit()

    stats["status"] = final_status.value
    stats["tokens_in"] = resultado.tokens_in
    stats["tokens_out"] = resultado.tokens_out

    logger.info(
        "analizar_bases_ok",
        codigo=codigo,
        status=final_status.value,
        tokens_in=resultado.tokens_in,
        tokens_out=resultado.tokens_out,
        duracion_ms=duracion_ms,
    )
    return stats


@celery_app.task(  # type: ignore[misc]
    name="tasks.analizar_bases.analizar_bases_licitacion",
    bind=True,
    autoretry_for=(LLMError,),
    retry_backoff=True,
    max_retries=2,
    acks_late=True,
)
def analizar_bases_licitacion(self: Any, codigo: str) -> dict[str, Any]:
    """Analiza las bases técnicas de una licitación con LLM.

    Lee los chunks embedidos de la licitación, los pasa al LLM junto con
    los criterios de evaluación registrados, y persiste el resultado
    estructurado en analisis_bases.

    Disparada automáticamente por marcar_licitacion_procesada al completar
    el pipeline PDF. También puede lanzarse manualmente.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.

    Returns:
        Dict con status, tokens_in, tokens_out.
    """
    logger.info("analizar_bases_start", codigo=codigo)
    return asyncio.run(_run(codigo))
