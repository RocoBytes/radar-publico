"""Enums de SQLAlchemy que reflejan los tipos ENUM de schema.sql.

Cada enum aquí corresponde a un CREATE TYPE en schema.sql.
Los valores deben coincidir exactamente (case-sensitive).
"""

import enum


class UserStatus(str, enum.Enum):
    """Estados de cuenta de usuario. Refleja user_status en schema.sql."""

    pending_activation = "pending_activation"
    active = "active"
    suspended = "suspended"
    deleted = "deleted"


class UserRole(str, enum.Enum):
    """Roles de usuario. Refleja user_role en schema.sql."""

    admin = "admin"
    proveedor = "proveedor"


class EmpresaTamano(str, enum.Enum):
    """Tamaño de empresa. Refleja empresa_tamano en schema.sql."""

    micro = "micro"
    pequena = "pequena"
    mediana = "mediana"
    grande = "grande"


class TicketStatus(str, enum.Enum):
    """Estado del ticket de ChileCompra. Refleja ticket_status en schema.sql."""

    pending = "pending"
    active = "active"
    error = "error"
    rate_limited = "rate_limited"
    expired = "expired"


class LicitacionEstado(str, enum.Enum):
    """Estado de licitación (interno). Refleja licitacion_estado en schema.sql."""

    publicada = "publicada"
    cerrada = "cerrada"
    desierta = "desierta"
    adjudicada = "adjudicada"
    revocada = "revocada"
    suspendida = "suspendida"
    desconocido = "desconocido"


class FechaTipo(str, enum.Enum):
    """Tipo de fecha de licitación. Refleja fecha_tipo en schema.sql."""

    creacion = "creacion"
    publicacion = "publicacion"
    preguntas_inicio = "preguntas_inicio"
    preguntas_fin = "preguntas_fin"
    respuestas = "respuestas"
    visita_terreno = "visita_terreno"
    cierre = "cierre"
    apertura_tecnica = "apertura_tecnica"
    apertura_economica = "apertura_economica"
    adjudicacion = "adjudicacion"
    firma_contrato = "firma_contrato"
    estimada_termino = "estimada_termino"


class OcEstado(str, enum.Enum):
    """Estado de orden de compra. Refleja oc_estado en schema.sql."""

    emitida = "emitida"
    aceptada = "aceptada"
    rechazada = "rechazada"
    cancelada = "cancelada"
    en_proceso = "en_proceso"
    recepcion_conforme = "recepcion_conforme"
    pagada = "pagada"
    desconocido = "desconocido"


class DocumentoTipo(str, enum.Enum):
    """Tipo de documento de bases. Refleja documento_tipo en schema.sql."""

    bases_administrativas = "bases_administrativas"
    bases_tecnicas = "bases_tecnicas"
    anexo = "anexo"
    aclaracion = "aclaracion"
    consulta = "consulta"
    respuesta = "respuesta"
    acta_apertura = "acta_apertura"
    acta_adjudicacion = "acta_adjudicacion"
    otro = "otro"


class DocumentoStatus(str, enum.Enum):
    """Estado de procesamiento de un documento.

    Refleja el tipo documento_status en schema.sql.
    """

    pendiente = "pendiente"
    descargado = "descargado"
    procesado = "procesado"
    error = "error"


class PipelineEstado(str, enum.Enum):
    """Estado de un ítem en el pipeline de seguimiento.

    Refleja el tipo pipeline_estado en schema.sql.
    """

    nueva = "nueva"
    vista = "vista"
    interesado = "interesado"
    postulando = "postulando"
    postulada = "postulada"
    adjudicada = "adjudicada"
    perdida = "perdida"
    descartada = "descartada"
