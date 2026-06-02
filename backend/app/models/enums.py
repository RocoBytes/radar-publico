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


class ChecklistItemEstado(str, enum.Enum):
    """Estado de un ítem del checklist documental.

    Refleja checklist_item_estado en la BD (migración 20260603_1000).
    """

    pendiente = "pendiente"
    en_preparacion = "en_preparacion"
    completado = "completado"
    no_aplica = "no_aplica"


class ChecklistItemOrigen(str, enum.Enum):
    """Origen de un ítem del checklist.

    Refleja checklist_item_origen en la BD (migración 20260603_1000).
    Permite futuro valor 'importado_excel' sin cambio de schema.
    """

    ia_generado = "ia_generado"
    manual = "manual"


class NotifTipo(str, enum.Enum):
    """Tipo de notificación. Refleja notif_tipo en schema.sql.

    cambio_estado_externo: ChileCompra cambió el estado de una licitación.
    cambio_estado_interno: el usuario movió una licitación en su pipeline.
    Migración 20260603_1030 renombró 'cambio_estado' → 'cambio_estado_externo'
    y reclasificó el histórico como interno.
    """

    nueva_oportunidad = "nueva_oportunidad"
    recordatorio_cierre = "recordatorio_cierre"
    cambio_estado_externo = "cambio_estado_externo"
    cambio_estado_interno = "cambio_estado_interno"
    adjudicacion_postulacion = "adjudicacion_postulacion"
    oportunidad_futura = "oportunidad_futura"
    sistema = "sistema"


class NotifCanal(str, enum.Enum):
    """Canal de envío de notificación. Refleja notif_canal en schema.sql."""

    email = "email"
    whatsapp = "whatsapp"
    in_app = "in_app"


class NotifStatus(str, enum.Enum):
    """Estado de una notificación. Refleja notif_status en schema.sql."""

    pendiente = "pendiente"
    enviada = "enviada"
    fallida = "fallida"
    leida = "leida"
    cancelada = "cancelada"


class MensajeRol(str, enum.Enum):
    """Rol de un mensaje en conversación IA. Refleja mensaje_rol en schema.sql."""

    user = "user"
    assistant = "assistant"
    system = "system"


class EmailFrecuencia(str, enum.Enum):
    """Frecuencia de envío de emails. Refleja email_frecuencia en schema.sql."""

    instantaneo = "instantaneo"
    diario = "diario"
    semanal = "semanal"


class AnalisisStatus(str, enum.Enum):
    """Estado de procesamiento de análisis IA (bases y borradores).

    Refleja analisis_status en schema.sql.
    """

    pendiente = "pendiente"
    procesando = "procesando"
    listo = "listo"
    error = "error"
