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

  // Cuando es true, el detalle aún se está sincronizando desde ChileCompra.
  // El cliente debe reintentar en ~10 segundos.
  detalle_pendiente?: boolean
}

export type LicitacionListResponse = {
  items: LicitacionListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// ── Módulo 1: Auto-análisis de bases técnicas ─────────────────────────────────

export type AnalisisStatus = "pendiente" | "procesando" | "listo" | "error"

export type RequisitoTecnico = {
  descripcion: string
  tipo: "obligatorio" | "deseable"
  detalle: string | null
}

export type CriterioExtraido = {
  nombre: string
  peso_pct: number
  descripcion: string | null
}

export type DocumentoObligatorio = {
  nombre: string
  descripcion: string | null
  obligatorio: boolean
}

export type PlazoClave = {
  tipo: string
  fecha_texto: string
  descripcion: string | null
}

export type AnalisisBases = {
  id: string
  licitacion_codigo: string
  version: number
  status: AnalisisStatus
  requisitos_tecnicos: RequisitoTecnico[] | null
  criterios_extraidos: CriterioExtraido[] | null
  documentos_obligatorios: DocumentoObligatorio[] | null
  plazos_clave: PlazoClave[] | null
  restricciones: string[] | null
  resumen_ejecutivo: string | null
  modelo_usado: string | null
  error_mensaje: string | null
  created_at: string
  updated_at: string
}

// ── Módulo 2: Borrador de propuesta técnica ───────────────────────────────────

export type SeccionPropuesta = {
  titulo: string
  contenido: string
  orden: number | null
}

export type BorradorPropuesta = {
  id: string
  licitacion_codigo: string
  empresa_id: string
  version: number
  status: AnalisisStatus
  titulo: string | null
  secciones: SeccionPropuesta[] | null
  documentos_pendientes: string[] | null
  notas_revision: string[] | null
  modelo_usado: string | null
  error_mensaje: string | null
  created_at: string
  updated_at: string
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
