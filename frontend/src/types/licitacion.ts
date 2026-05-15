export type LicitacionEstado =
  | "publicada"
  | "cerrada"
  | "desierta"
  | "adjudicada"
  | "revocada"
  | "suspendida"

export type LicitacionListItem = {
  codigo: string
  nombre: string
  estado: LicitacionEstado
  tipo: string | null
  moneda: string
  monto_estimado: number | null
  fecha_publicacion: string | null
  fecha_cierre: string | null
  organismo_nombre: string | null
  region_nombre: string | null
  score: number | null
}

export type LicitacionItem = {
  id: string
  numero_item: number
  descripcion: string | null
  unidad: string | null
  cantidad: number | null
  unspsc_codigo: string | null
}

export type DocumentoBase = {
  id: string
  nombre: string
  url_r2: string | null
  url_portal: string | null
  procesado: boolean
}

export type LicitacionFecha = {
  tipo: string
  fecha: string
}

export type LicitacionDetalle = LicitacionListItem & {
  descripcion: string | null
  unidad_nombre: string | null
  items: LicitacionItem[]
  documentos: DocumentoBase[]
  fechas: LicitacionFecha[]
}

export type LicitacionListResponse = {
  items: LicitacionListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export type LicitacionFiltros = {
  q?: string
  estado?: LicitacionEstado
  tipo?: string
  fecha_desde?: string
  fecha_hasta?: string
  monto_min?: number
  monto_max?: number
  unspsc_codigo?: string
  region?: string
  page?: number
  page_size?: number
}
