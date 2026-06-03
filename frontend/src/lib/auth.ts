/**
 * Helpers de autenticación del lado cliente.
 * Se implementa en Sprint 1 con JWT + refresh tokens.
 * Tokens en cookies httpOnly (regla de oro — NO localStorage).
 */

export function isAuthenticated(): boolean {
  // Sprint 1: verificar cookie de sesión vía endpoint /api/v1/auth/me
  return false;
}
