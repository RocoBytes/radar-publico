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

export interface TicketStatus {
  tiene_ticket: boolean
  status: string | null
  ticket_ultimos_4: string | null
  cargado_at: string | null
  ultima_validacion_at: string | null
  ultimo_error: string | null
  cuota_diaria_max: number | null
  requests_hoy: number
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
