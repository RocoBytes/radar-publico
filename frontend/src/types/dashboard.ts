export type LicitacionEnTop = {
  codigo: string
  nombre: string
  estado: string
  fecha_cierre: string | null
  monto_estimado: number | null
  organismo_nombre: string | null
}

export type TopOportunidad = {
  id: string
  score: number | null
  estado: string
  licitacion: LicitacionEnTop
}

export type DashboardResumen = {
  oportunidades_activas: number
  nuevas_hoy: number
  proximas_a_cerrar: number
  en_pipeline: number
  top_oportunidades: TopOportunidad[]
  ultima_sincronizacion: string | null
}

export type SegmentoItem = {
  codigo: string
  nombre: string
  cantidad: number
}

export type DashboardSegmentos = {
  segmentos: SegmentoItem[]
}
