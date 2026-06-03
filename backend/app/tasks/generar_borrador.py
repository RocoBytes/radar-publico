"""Tarea Celery: generación de borrador de propuesta técnica con LLM.

Decisiones de diseño:

1. DEPENDENCIA: requiere analisis_bases en status='listo' para la licitación.
   Si el análisis no está listo, la tarea falla con estado 'error'.

2. POR EMPRESA: a diferencia de analisis_bases (por licitación), el borrador
   es per-empresa. empresa_id se pasa como argumento desde el endpoint.

3. SESIONES: misma estrategia que analizar_bases — dos sesiones separadas,
   LLM fuera de cualquier sesión de BD.

4. TOKENS: el borrador es más largo que el análisis. max_tokens=6000.

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

_BORRADOR_VERSION = 1
_BORRADOR_MAX_TOKENS = 6000


async def _run(codigo: str, empresa_id_str: str) -> dict[str, Any]:
    """Lógica async: genera el borrador de propuesta técnica con LLM."""
    import uuid

    from sqlalchemy import select

    from app.db.session import AsyncSessionLocal
    from app.models.analisis_ia import AnalisisBases, BorradorPropuesta
    from app.models.empresa import Empresa
    from app.models.enums import AnalisisStatus
    from app.services.llm.client import completion
    from app.services.llm.prompts import BORRADOR_PROPUESTA
    from app.services.llm.usage_log import registrar_uso

    empresa_uuid = uuid.UUID(empresa_id_str)

    stats: dict[str, Any] = {
        "licitacion_codigo": codigo,
        "empresa_id": empresa_id_str,
        "status": "skip",
        "tokens_in": 0,
        "tokens_out": 0,
    }

    # ── Sesión 1: verificar idempotencia, cargar datos, marcar 'procesando' ──
    borrador_id: Any = None
    analisis_texto: str = ""
    perfil_empresa: str = ""

    async with AsyncSessionLocal() as session:
        # Verificar idempotencia
        result = await session.execute(
            select(BorradorPropuesta).where(
                BorradorPropuesta.licitacion_codigo == codigo,
                BorradorPropuesta.empresa_id == empresa_uuid,
                BorradorPropuesta.version == _BORRADOR_VERSION,
            )
        )
        borrador: BorradorPropuesta | None = result.scalar_one_or_none()

        if borrador and borrador.status in (AnalisisStatus.listo, AnalisisStatus.procesando):
            stats["status"] = borrador.status.value
            logger.debug("generar_borrador_skip", codigo=codigo, status=borrador.status)
            return stats

        # El análisis debe estar listo
        analisis_result = await session.execute(
            select(AnalisisBases).where(
                AnalisisBases.licitacion_codigo == codigo,
                AnalisisBases.version == 1,
                AnalisisBases.status == AnalisisStatus.listo,
            )
        )
        analisis: AnalisisBases | None = analisis_result.scalar_one_or_none()

        if analisis is None:
            logger.warning("generar_borrador_sin_analisis", codigo=codigo)
            stats["status"] = "analisis_no_disponible"
            return stats

        # Cargar empresa
        empresa: Empresa | None = await session.get(Empresa, empresa_uuid)
        if empresa is None:
            logger.warning("generar_borrador_empresa_no_encontrada", empresa_id=empresa_id_str)
            stats["status"] = "empresa_no_encontrada"
            return stats

        # Extraer datos del análisis a texto ANTES del commit
        analisis_id = analisis.id
        analisis_texto = _formatear_analisis(analisis)

        # Extraer perfil de empresa a texto ANTES del commit
        perfil_empresa = _formatear_empresa(empresa)

        # Crear o resetear borrador
        ahora = datetime.now(UTC)
        if borrador is None:
            borrador = BorradorPropuesta(
                licitacion_codigo=codigo,
                empresa_id=empresa_uuid,
                analisis_id=analisis_id,
                version=_BORRADOR_VERSION,
                status=AnalisisStatus.procesando,
                created_at=ahora,
                updated_at=ahora,
            )
            session.add(borrador)
        else:
            borrador.status = AnalisisStatus.procesando
            borrador.analisis_id = analisis_id
            borrador.error_mensaje = None
            borrador.updated_at = ahora

        await session.flush()
        borrador_id = borrador.id
        await session.commit()

    # ── Llamada al LLM (fuera de sesión) ──────────────────────────────────────

    prompt_text = BORRADOR_PROPUESTA.render(
        analisis_bases=analisis_texto,
        perfil_empresa=perfil_empresa,
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt_text}]
    inicio = datetime.now(UTC)

    try:
        resultado = await completion(
            messages,
            max_tokens=_BORRADOR_MAX_TOKENS,
            temperature=0.3,
        )
    except (LLMError, LLMRateLimitError) as exc:
        async with AsyncSessionLocal() as session:
            borrador_db: BorradorPropuesta | None = await session.get(
                BorradorPropuesta, borrador_id
            )
            if borrador_db:
                borrador_db.status = AnalisisStatus.error
                borrador_db.error_mensaje = str(exc)[:2000]
                borrador_db.updated_at = datetime.now(UTC)
                await session.commit()
        logger.error("generar_borrador_llm_error", codigo=codigo, error=str(exc))
        raise

    duracion_ms = int((datetime.now(UTC) - inicio).total_seconds() * 1000)

    # ── Parsear JSON ───────────────────────────────────────────────────────────

    datos: dict[str, Any] = {}
    parse_error: str | None = None
    try:
        raw = resultado.content.strip()
        if raw.startswith("```"):
            partes = raw.split("```")
            raw = partes[1]
            if raw.startswith("json"):
                raw = raw[4:]
        datos = json.loads(raw)
    except json.JSONDecodeError as exc:
        parse_error = f"JSON inválido: {exc!s}"
        logger.error("generar_borrador_json_error", codigo=codigo, error=parse_error)

    # ── Sesión 2: persistir resultado ─────────────────────────────────────────

    async with AsyncSessionLocal() as session:
        borrador_db = await session.get(BorradorPropuesta, borrador_id)
        if borrador_db is None:
            logger.error("generar_borrador_registro_perdido", codigo=codigo)
            stats["status"] = "error_registro_perdido"
            return stats

        if parse_error:
            borrador_db.status = AnalisisStatus.error
            borrador_db.error_mensaje = parse_error
        else:
            borrador_db.status = AnalisisStatus.listo
            borrador_db.titulo = datos.get("titulo")
            borrador_db.secciones = datos.get("secciones")
            borrador_db.documentos_pendientes = datos.get("documentos_pendientes")
            borrador_db.notas_revision = datos.get("notas_revision")

        borrador_db.modelo_usado = resultado.modelo
        borrador_db.prompt_version = BORRADOR_PROPUESTA.version
        borrador_db.tokens_input = resultado.tokens_in
        borrador_db.tokens_output = resultado.tokens_out
        borrador_db.updated_at = datetime.now(UTC)

        final_status = borrador_db.status

        await registrar_uso(
            session,
            provider="anthropic",
            modelo=resultado.modelo,
            tokens_in=resultado.tokens_in,
            tokens_out=resultado.tokens_out,
            empresa_id=empresa_uuid,
            feature="generar_borrador_propuesta",
            duracion_ms=duracion_ms,
        )
        await session.commit()

    stats["status"] = final_status.value
    stats["tokens_in"] = resultado.tokens_in
    stats["tokens_out"] = resultado.tokens_out

    logger.info(
        "generar_borrador_ok",
        codigo=codigo,
        status=final_status.value,
        tokens_in=resultado.tokens_in,
        duracion_ms=duracion_ms,
    )
    return stats


def _formatear_analisis(
    analisis: "AnalisisBases",  # type: ignore[name-defined]  # noqa: F821
) -> str:
    """Convierte el análisis a texto estructurado para el prompt."""
    partes: list[str] = []

    if analisis.resumen_ejecutivo:
        partes.append(f"RESUMEN:\n{analisis.resumen_ejecutivo}")

    if analisis.criterios_extraidos:
        criterios = "\n".join(
            f"- {c.get('nombre', '')}: {c.get('peso_pct', 0)}%"
            + (f" — {c.get('descripcion', '')}" if c.get("descripcion") else "")
            for c in analisis.criterios_extraidos
        )
        partes.append(f"CRITERIOS DE EVALUACIÓN:\n{criterios}")

    if analisis.requisitos_tecnicos:
        reqs = "\n".join(
            f"- [{r.get('tipo', 'obligatorio').upper()}] {r.get('descripcion', '')}"
            for r in analisis.requisitos_tecnicos
        )
        partes.append(f"REQUISITOS TÉCNICOS:\n{reqs}")

    if analisis.documentos_obligatorios:
        docs = "\n".join(f"- {d.get('nombre', '')}" for d in analisis.documentos_obligatorios)
        partes.append(f"DOCUMENTOS REQUERIDOS:\n{docs}")

    if analisis.restricciones:
        partes.append("RESTRICCIONES:\n" + "\n".join(f"- {r}" for r in analisis.restricciones))

    return "\n\n".join(partes) or "Análisis no disponible."


def _formatear_empresa(
    empresa: "Empresa",  # type: ignore[name-defined]  # noqa: F821
) -> str:
    """Convierte el perfil de empresa a texto estructurado para el prompt."""
    lineas = [
        f"- Razón social: {empresa.razon_social}",
        f"- RUT: {empresa.rut}",
    ]
    if empresa.tamano:
        lineas.append(f"- Tamaño: {empresa.tamano.value}")
    if empresa.giros:
        lineas.append(f"- Giros / rubros: {', '.join(empresa.giros)}")
    if empresa.ano_fundacion:
        lineas.append(f"- Año de fundación: {empresa.ano_fundacion}")
    if empresa.numero_empleados:
        lineas.append(f"- Número de empleados: {empresa.numero_empleados}")
    if empresa.regiones_operacion:
        lineas.append(f"- Regiones de operación: {', '.join(empresa.regiones_operacion)}")
    if empresa.inscrito_chileproveedores:
        lineas.append("- Inscrito en ChileProveedores: Sí")
    if empresa.sello_empresa_mujer:
        lineas.append("- Sello Empresa Mujer: Sí")
    if empresa.certificaciones:
        certs = json.dumps(empresa.certificaciones, ensure_ascii=False)
        lineas.append(f"- Certificaciones: {certs}")

    return "\n".join(lineas)


@celery_app.task(  # type: ignore[untyped-decorator]
    name="tasks.generar_borrador.generar_borrador_propuesta",
    bind=True,
    autoretry_for=(LLMError,),
    retry_backoff=True,
    max_retries=2,
    acks_late=True,
)
def generar_borrador_propuesta(self: Any, codigo: str, empresa_id: str) -> dict[str, Any]:
    """Genera un borrador de propuesta técnica con LLM para una empresa.

    Requiere que el análisis de bases (analisis_bases) esté en status='listo'.
    El borrador es personalizado con el perfil de la empresa.

    Args:
        codigo: Código de la licitación, ej: '1000-8-LE26'.
        empresa_id: UUID de la empresa, en formato string.

    Returns:
        Dict con status, tokens_in, tokens_out.
    """
    logger.info("generar_borrador_start", codigo=codigo, empresa_id=empresa_id)
    return asyncio.run(_run(codigo, empresa_id))
