export type UserRole = "admin" | "proveedor";
export type UserStatus = "active" | "suspended" | "pending";

export type EmpresaResumen = {
  rut: string;
  razon_social: string;
  tiene_ticket: boolean;
};

export type CuentaResponse = {
  id: string;
  email: string;
  rol: UserRole;
  status: UserStatus;
  must_change_password: boolean;
  created_at: string;
  empresa: EmpresaResumen | null;
};

export type CuentaCreadaResponse = CuentaResponse & {
  temp_password: string;
};

export type CuentaListResponse = {
  items: CuentaResponse[];
  total: number;
  page: number;
  page_size: number;
};

export type CrearCuentaPayload = {
  email: string;
  rut: string;
  razon_social: string;
};

export type TicketResponse = {
  id: string;
  ticket_ultimos_4: string;
  status: string;
  created_at: string;
};

export type ImpersonacionResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type TicketDiagnosticoResponse = {
  tiene_ticket: boolean;
  ticket_ultimos_4: string | null;
  ticket_status: string | null;
  llamadas_hoy: number;
  test_ok: boolean | null;
  test_error: string | null;
  test_duracion_ms: number | null;
};
