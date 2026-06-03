export interface RenovacionItem {
  licitacion_codigo: string
  nombre: string
  organismo_nombre: string | null
  monto_estimado: number | null
  fecha_adjudicacion: string | null
  duracion_estimada_meses: number | null
  fecha_estimada_termino_contrato: string | null
  dias_para_termino: number | null
}

export interface RenovacionesListResponse {
  total: number
  page: number
  page_size: number
  items: RenovacionItem[]
}

export interface PlanAnualLinea {
  id: string
  ano: number
  codigo_organismo: number
  descripcion: string
  unspsc_codigo: string | null
  unspsc_nombre: string | null
  monto_estimado: number | null
  moneda: string
  mes_estimado: number | null
  modalidad: string | null
  status: "planificada" | "publicada" | "adjudicada" | "cancelada"
  licitacion_codigo: string | null
  created_at: string
}

export interface PlanAnualListResponse {
  total: number
  page: number
  page_size: number
  items: PlanAnualLinea[]
}
