export type EmpresaTamano = "micro" | "pequena" | "mediana" | "grande"

export interface EmpresaProfile {
  id: string
  rut: string
  razon_social: string
  nombre_fantasia: string | null
  giros: string[] | null
  tamano: EmpresaTamano | null
  ano_fundacion: number | null
  numero_empleados: number | null
  regiones_operacion: string[]
  sello_empresa_mujer: boolean
  inscrito_chileproveedores: boolean
  contacto_telefono: string | null
  contacto_direccion: string | null
  onboarding_completado: boolean
}

export interface EmpresaUpdateRequest {
  nombre_fantasia?: string | null
  giros?: string[] | null
  tamano?: EmpresaTamano | null
  ano_fundacion?: number | null
  numero_empleados?: number | null
  regiones_operacion?: string[]
  sello_empresa_mujer?: boolean
  inscrito_chileproveedores?: boolean
  contacto_telefono?: string | null
  contacto_direccion?: string | null
  onboarding_completado?: boolean
}
