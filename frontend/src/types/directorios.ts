export interface OrganismoListItem {
  codigo_organismo: number
  nombre: string
  ministerio: string | null
  region: string | null
  total_licitaciones: number
  monto_total_adjudicado: number | null
  proveedores_distintos: number
}

export interface OrganismosResponse {
  items: OrganismoListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface ProveedorListItem {
  rut: string
  razon_social: string
  nombre_fantasia: string | null
  licitaciones_ganadas: number
  monto_total: number | null
}

export interface ProveedoresResponse {
  items: ProveedorListItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}
