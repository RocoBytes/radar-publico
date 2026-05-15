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
