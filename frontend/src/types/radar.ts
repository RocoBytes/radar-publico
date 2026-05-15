export type NotifCanal = "email" | "whatsapp" | "in_app"
export type NotifFrecuencia = "instantaneo" | "diario" | "semanal"

export type RadarFiltros = {
  q?: string
  estado?: string
  tipo?: string
  monto_min?: number
  monto_max?: number
  unspsc_codigo?: string
  region?: string
}

export type Radar = {
  id: string
  nombre: string
  descripcion: string | null
  filtros: RadarFiltros
  activo: boolean
  notif_canal: NotifCanal
  notif_frecuencia: NotifFrecuencia
  notif_score_minimo: number
  ultima_ejecucion_at: string | null
  created_at: string
  updated_at: string
}

export type RadarListResponse = {
  items: Radar[]
  total: number
}

export type RadarCreateRequest = {
  nombre: string
  descripcion?: string
  filtros: RadarFiltros
  notif_canal?: NotifCanal
  notif_frecuencia?: NotifFrecuencia
  notif_score_minimo?: number
}

export type RadarUpdateRequest = Partial<RadarCreateRequest> & {
  activo?: boolean
}
