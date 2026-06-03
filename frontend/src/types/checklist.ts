export type ChecklistItemEstado =
  | "pendiente"
  | "en_preparacion"
  | "completado"
  | "no_aplica"

export type ChecklistItemOrigen = "ia_generado" | "manual"

export type ChecklistItem = {
  id: string
  pipeline_item_id: string
  nombre: string
  descripcion: string | null
  obligatorio: boolean
  estado: ChecklistItemEstado
  origen: ChecklistItemOrigen
  orden: number
  completed_at: string | null
  created_at: string
  updated_at: string
}

export type ChecklistBootstrapResponse = {
  creados: number
  omitidos: number
  items: ChecklistItem[]
}

export type ChecklistItemCreateRequest = {
  nombre: string
  descripcion?: string
  obligatorio?: boolean
  orden?: number
}

export type ChecklistItemUpdateRequest = {
  nombre?: string
  descripcion?: string
  obligatorio?: boolean
  estado?: ChecklistItemEstado
  orden?: number
}
