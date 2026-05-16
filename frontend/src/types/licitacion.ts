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
  modalidad: string | null
  es_renovable: boolean
  duracion_estimada_meses: number | null

  // Unidad compradora
  unidad_compra: string | null
  rut_unidad: string | null

  // Organismo demandante
  organismo_rut: string | null
  organismo_region: string | null
  organismo_comuna: string | null
  organismo_direccion: string | null
  organismo_ministerio: string | null

  // Contacto
  contacto_nombre: string | null
  contacto_email: string | null
  contacto_telefono: string | null

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
