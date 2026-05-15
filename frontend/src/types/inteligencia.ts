export interface TopProveedor {
  rut: string
  razon_social: string
  licitaciones_ganadas: number
  monto_total: number | null
}

export interface InteligenciaData {
  organismo_nombre: string | null
  total_licitaciones_organismo: number
  monto_promedio_organismo: number | null
  top_proveedores: TopProveedor[]
}
