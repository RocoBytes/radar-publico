export type NotifTipo =
  | "nueva_oportunidad"
  | "recordatorio_cierre"
  | "cambio_estado"
  | "adjudicacion_postulacion"
  | "oportunidad_futura"
  | "sistema"

export type NotifStatus =
  | "pendiente"
  | "enviada"
  | "fallida"
  | "leida"
  | "cancelada"

export type Notificacion = {
  id: string
  tipo: NotifTipo
  canal: "email" | "whatsapp" | "in_app"
  status: NotifStatus
  titulo: string
  cuerpo: string
  licitacion_codigo: string | null
  radar_id: string | null
  leida_at: string | null
  created_at: string
}

export type NotificacionesResumen = {
  unread_count: number
  items: Notificacion[]
}
