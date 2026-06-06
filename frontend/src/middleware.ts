import { type NextRequest, NextResponse } from "next/server"

/**
 * Middleware de autenticación para Radar Público.
 *
 * Flujo (solo chequeos estáticos, sin fetch de red):
 * 1. Rutas públicas, /api/* y raíz → dejar pasar siempre
 * 2. access_token presente y no expirado → dejar pasar
 * 3. refresh_token presente y no expirado → dejar pasar
 *    El cliente disparará el refresh cuando el backend devuelva 401,
 *    usando el interceptor de apiFetch → Route Handler /api/auth/refresh.
 * 4. Sin ningún token válido → redirect a /login
 *
 * Por qué eliminamos el fetch bloqueante:
 * El refresh en el middleware duplicaba la latencia de cada transición de
 * página (fetch a la red interna de Docker en el critical path de routing).
 * El interceptor client-side en apiFetch maneja el mismo escenario sin
 * bloquear el rendering: recibe 401 del backend, llama /api/auth/refresh,
 * y reintenta el request original con skipRefresh: true.
 */

const PUBLIC_PATHS = [
  "/login",
  "/forgot-password",
  "/reset-password",
  "/change-password",
]

/**
 * Decodifica el payload del JWT y verifica si está expirado.
 * No valida la firma — eso es responsabilidad del backend.
 */
function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return true
    // JWT usa base64url — normalizar a base64 estándar antes de decodificar
    const base64 = parts[1]!.replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(base64)) as { exp?: number }
    return typeof payload.exp !== "number" || payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl

  // Dejar pasar rutas públicas, las rutas de API (Route Handlers) y la raíz
  const isPublic =
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/api/") ||
    pathname === "/"

  if (isPublic) {
    return NextResponse.next()
  }

  const accessToken = request.cookies.get("access_token")?.value
  const refreshToken = request.cookies.get("refresh_token")?.value

  // access_token vigente → caso feliz, sin ningún fetch
  if (accessToken && !isTokenExpired(accessToken)) {
    return NextResponse.next()
  }

  // access_token expirado pero refresh_token vigente → dejar pasar.
  // El backend devolverá 401 al primer request de datos; el interceptor en
  // apiFetch disparará POST /api/auth/refresh y reintentará con skipRefresh.
  if (refreshToken && !isTokenExpired(refreshToken)) {
    return NextResponse.next()
  }

  // Sin ningún token válido → no hay forma de recuperar la sesión
  return NextResponse.redirect(new URL("/login", request.url))
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
}
