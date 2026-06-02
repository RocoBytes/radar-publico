"""Schemas Pydantic para los endpoints de licitaciones.

Expone solo campos públicos — excluye campos internos del pipeline:
raw_payload, search_vector, embedding, hash_contenido,
bases_descargadas_at, bases_procesadas_at, detalle_sincronizado_at.

Nota: uuid, datetime y los enums se importan en runtime porque Pydantic v2
los necesita para construir los schemas. Los noqa: TCH* son intencionales.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TCH003
import uuid  # noqa: TCH003

from pydantic import BaseModel, ConfigDict

from app.models.enums import AnalisisStatus, FechaTipo, LicitacionEstado  # noqa: TCH001


class LicitacionListItem(BaseModel):
    """Item resumido para el listado de licitaciones."""

    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    estado: LicitacionEstado
    tipo: str | None
    modalidad: str | None
    moneda: str
    monto_estimado: float | None
    fecha_publicacion: datetime | None
    fecha_cierre: datetime | None
    fecha_adjudicacion: datetime | None
    # Campo poblado manualmente desde el join con organismos
    organismo_nombre: str | None = None
    created_at: datetime
    updated_at: datetime


class LicitacionListResponse(BaseModel):
    """Respuesta paginada del listado de licitaciones."""

    model_config = ConfigDict(from_attributes=True)

    items: list[LicitacionListItem]
    total: int
    page: int
    page_size: int


class LicitacionFechaResponse(BaseModel):
    """Fecha del calendario de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: FechaTipo
    fecha: datetime
    es_estimada: bool


class LicitacionItemResponse(BaseModel):
    """Item de línea de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    numero_item: int
    unspsc_codigo: str | None
    unspsc_nombre: str | None
    nombre_producto: str | None
    descripcion: str | None
    cantidad: float | None
    unidad: str | None
    monto_unitario_estimado: float | None


class CriterioEvaluacionResponse(BaseModel):
    """Criterio de evaluación de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nombre: str
    ponderacion: float
    tipo: str | None
    orden: int | None


class LicitacionDetalleResponse(BaseModel):
    """Detalle completo de una licitación con sus relaciones."""

    model_config = ConfigDict(from_attributes=True)

    # Identificación
    codigo: str
    nombre: str
    estado: LicitacionEstado
    descripcion: str | None

    # Características
    tipo: str | None
    modalidad: str | None
    moneda: str
    monto_estimado: float | None
    es_renovable: bool
    duracion_estimada_meses: int | None

    # Fechas clave
    fecha_publicacion: datetime | None
    fecha_cierre: datetime | None
    fecha_adjudicacion: datetime | None

    # Unidad compradora (datos de la licitación)
    unidad_compra: str | None
    rut_unidad: str | None

    # Organismo demandante (join con tabla organismos)
    organismo_nombre: str | None = None
    organismo_rut: str | None = None
    organismo_region: str | None = None
    organismo_comuna: str | None = None
    organismo_direccion: str | None = None
    organismo_ministerio: str | None = None

    # Contacto
    contacto_nombre: str | None
    contacto_email: str | None
    contacto_telefono: str | None

    created_at: datetime
    updated_at: datetime

    # Relaciones
    items: list[LicitacionItemResponse]
    fechas: list[LicitacionFechaResponse]
    criterios: list[CriterioEvaluacionResponse]

    # Indica que el detalle completo aún no fue sincronizado y está en proceso.
    # El cliente debe reintentar en ~10 segundos cuando este campo es True.
    detalle_pendiente: bool = False


# ── Módulo 1: Auto-análisis de bases técnicas ─────────────────────────────────


class RequisitoTecnico(BaseModel):
    """Requisito técnico extraído de las bases."""

    descripcion: str
    tipo: str  # "obligatorio" | "deseable"
    detalle: str | None = None


class CriterioExtraido(BaseModel):
    """Criterio de evaluación extraído de las bases con su peso."""

    nombre: str
    peso_pct: float
    descripcion: str | None = None


class DocumentoObligatorio(BaseModel):
    """Documento requerido para la presentación de la oferta."""

    nombre: str
    descripcion: str | None = None
    obligatorio: bool = True


class PlazoClave(BaseModel):
    """Hito o plazo crítico del proceso licitatorio."""

    tipo: str
    fecha_texto: str
    descripcion: str | None = None


class AnalisisBasesResponse(BaseModel):
    """Resultado del análisis LLM de las bases técnicas de una licitación."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    licitacion_codigo: str
    version: int
    status: AnalisisStatus
    requisitos_tecnicos: list[RequisitoTecnico] | None = None
    criterios_extraidos: list[CriterioExtraido] | None = None
    documentos_obligatorios: list[DocumentoObligatorio] | None = None
    plazos_clave: list[PlazoClave] | None = None
    restricciones: list[str] | None = None
    resumen_ejecutivo: str | None = None
    modelo_usado: str | None = None
    prompt_version: int | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    error_mensaje: str | None = None
    created_at: datetime
    updated_at: datetime


# ── Módulo 2: Borrador de propuesta técnica ───────────────────────────────────


class SeccionPropuesta(BaseModel):
    """Sección estructurada del borrador de propuesta técnica."""

    titulo: str
    contenido: str
    orden: int | None = None


class BorradorPropuestaResponse(BaseModel):
    """Resultado del borrador de propuesta técnica generado con LLM."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    licitacion_codigo: str
    empresa_id: uuid.UUID
    version: int
    status: AnalisisStatus
    titulo: str | None = None
    secciones: list[SeccionPropuesta] | None = None
    documentos_pendientes: list[str] | None = None
    notas_revision: list[str] | None = None
    modelo_usado: str | None = None
    tokens_input: int | None = None
    tokens_output: int | None = None
    error_mensaje: str | None = None
    created_at: datetime
    updated_at: datetime
