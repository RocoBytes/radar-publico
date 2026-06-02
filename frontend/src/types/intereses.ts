export type InteresTipo =
  | "unspsc_segmento"
  | "unspsc_familia"
  | "unspsc_clase"
  | "unspsc_commodity"
  | "keyword"
  | "ejemplo_codigo"

export interface Interes {
  id: string
  tipo: InteresTipo
  valor: string
  prioridad: number
  created_at: string
}

export interface InteresCreateRequest {
  tipo: InteresTipo
  valor: string
  prioridad?: number
}

export interface InteresListResponse {
  items: Interes[]
  total: number
}
