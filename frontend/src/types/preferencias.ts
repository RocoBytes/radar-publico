export type EmailFrecuencia = "instantaneo" | "diario" | "semanal"

export interface PreferenciasNotificaciones {
  email_activo: boolean
  email_frecuencia: EmailFrecuencia
  email_score_minimo: number | null
  whatsapp_activo: boolean
  whatsapp_solo_criticas: boolean
  whatsapp_score_minimo: number | null
  in_app_activo: boolean
  tipos_activos: string[]
  updated_at: string
}

export interface PreferenciasUpdateRequest {
  email_activo?: boolean
  email_frecuencia?: EmailFrecuencia
  email_score_minimo?: number | null
  whatsapp_activo?: boolean
  whatsapp_solo_criticas?: boolean
  whatsapp_score_minimo?: number | null
  in_app_activo?: boolean
  tipos_activos?: string[]
}
