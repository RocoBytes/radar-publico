export interface AdminKpis {
  empresas_activas: number;
  licitaciones_indexadas: number;
  mensajes_ia_hoy: number;
  costo_ia_mes: number; // CLP
}

export interface CostoIaEmpresa {
  empresa_id: string;
  razon_social: string;
  mensajes_mes: number;
  tokens_input_mes: number;
  tokens_output_mes: number;
  costo_mes: number; // CLP
}

export interface AdminCostosIaResponse {
  meses: number;
  empresas: CostoIaEmpresa[];
}
