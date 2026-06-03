export type TipoItemAdmisibilidad = "restriccion" | "documento" | "requisito"
export type UrgenciaAdmisibilidad = "alta" | "media" | "baja"
export type NivelRiesgo = "bajo" | "medio" | "alto"

export interface ItemAdmisibilidad {
  tipo: TipoItemAdmisibilidad
  descripcion: string
  urgencia: UrgenciaAdmisibilidad
}

export interface InadmisibilidadData {
  analisis_disponible: boolean
  nivel_riesgo: NivelRiesgo | null
  items: ItemAdmisibilidad[]
  resumen: string | null
}

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
  // Módulo 3: datos de adjudicaciones reales
  proveedores_unicos_organismo: number
  precio_min_organismo: number | null
  precio_max_organismo: number | null
  top_competidores_rubro: TopProveedor[]
}
