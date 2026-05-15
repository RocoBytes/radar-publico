export interface TendenciaMes {
  mes: string
  cantidad: number
  monto_total: number | null
}

export interface TendenciaResponse {
  datos: TendenciaMes[]
}

export interface TopOrganismo {
  nombre: string
  cantidad: number
  monto_total: number | null
}

export interface TopOrganismosResponse {
  organismos: TopOrganismo[]
}
