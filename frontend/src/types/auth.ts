/**
 * Tipos TypeScript derivados de los DTOs del backend (backend/app/schemas/auth.py).
 * Mantener sincronizados con el backend — no modificar estructura sin actualizar ambos lados.
 */

/** Roles disponibles en el sistema */
export type UserRole = "proveedor" | "admin"

/** Información básica de la empresa del usuario */
export type EmpresaBasica = {
  id: string
  rut: string
  razon_social: string
}

/** Perfil del usuario autenticado */
export type UserMe = {
  id: string
  email: string
  rol: UserRole
  must_change_password: boolean
  empresa: EmpresaBasica | null
}

/** Respuesta del endpoint de login */
export type LoginResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  must_change_password: boolean
}

/** Respuesta del endpoint de refresh de token */
export type RefreshResponse = {
  access_token: string
  refresh_token: string
  token_type: string
}

/** Error estándar de la API */
export type ApiError = {
  detail: string
}
