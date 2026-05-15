export type PipelineEstado =
  | "nueva"
  | "evaluando"
  | "interesada"
  | "postulando"
  | "postulada"
  | "ganada"
  | "perdida"
  | "descartada"

export type PipelineNota = {
  id: string
  contenido: string
  created_at: string
}

export type LicitacionEnPipeline = {
  codigo: string
  nombre: string
  estado: string
  tipo: string | null
  moneda: string
  monto_estimado: number | null
  fecha_publicacion: string | null
  fecha_cierre: string | null
  organismo_nombre: string | null
}

export type PipelineListItem = {
  id: string
  estado: PipelineEstado
  score: number | null
  score_justificacion: Record<string, unknown> | null
  razon_descarte: string | null
  monto_postulado: number | null
  resultado_observaciones: string | null
  detected_by_radar_id: string | null
  notas_count: number
  created_at: string
  updated_at: string
  licitacion: LicitacionEnPipeline
}

export type PipelineItemDetail = PipelineListItem & {
  notas: PipelineNota[]
}

export type PipelineListResponse = {
  items: PipelineListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type PipelineItemUpdateRequest = {
  estado?: PipelineEstado
  razon_descarte?: string
  monto_postulado?: number
  resultado_observaciones?: string
}

export type PipelineItemCreateRequest = {
  licitacion_codigo: string
}
