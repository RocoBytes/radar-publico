import { type NextRequest, NextResponse } from "next/server"

/**
 * Middleware de autenticación para Radar Público.
 *
 * Flujo:
 * 1. Rutas públicas y /api/* → dejar pasar siempre
 * 2. access_token presente y no expirado → dejar pasar sin fetch
 * 3. access_token ausente o expirado + refresh_token presente → intentar refresh
 *    - Si el refresh tiene éxito: setear nueva cookie y continuar
 *    - Si el refresh falla: redirect a /login
 * 4. Sin ningún token → redirect a /login
 *
 * IMPORTANTE: No usar `export const runtime = 'edge'` porque hacemos fetch a
 * http:// (red Docker interna). Edge runtime no soporta fetch a URLs http://.
 */

const PUBLIC_PATHS = [
  "/login",
  "/forgot-password",
  "/reset-password",
  "/change-password",
]

const INTERNAL_API_URL =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

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

/**
 * Intenta refrescar el access_token usando el refresh_token.
 * Llama al backend interno directamente (http:// en red Docker).
 * Devuelve el nuevo access_token o null si el refresh falló.
 */
async function refreshAccessToken(
  refreshToken: string
): Promise<string | null> {
  try {
    const response = await fetch(
      `${INTERNAL_API_URL}/api/v1/auth/refresh`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }
    )
    if (!response.ok) return null
    const data = (await response.json()) as { access_token?: string }
    return data.access_token ?? null
  } catch {
    return null
  }
}

export async function middleware(request: NextRequest): Promise<NextResponse> {
  const { pathname } = request.nextUrl

  // Dejar pasar rutas públicas y las rutas de API (Route Handlers)
  const isPublic =
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/api/") ||
    pathname === "/"

  if (isPublic) {
    return NextResponse.next()
  }

  const accessToken = request.cookies.get("access_token")?.value
  const refreshToken = request.cookies.get("refresh_token")?.value

  // Caso feliz: access_token presente y vigente → dejar pasar sin ningún fetch
  if (accessToken && !isTokenExpired(accessToken)) {
    return NextResponse.next()
  }

  // Sin refresh_token → no hay forma de recuperar la sesión
  if (!refreshToken) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  // access_token ausente o expirado, pero hay refresh_token → intentar refresh
  const newAccessToken = await refreshAccessToken(refreshToken)

  if (!newAccessToken) {
    // Refresh falló (refresh_token expirado o inválido)
    return NextResponse.redirect(new URL("/login", request.url))
  }

  // Refresh exitoso: continuar con la respuesta y setear la nueva cookie
  const response = NextResponse.next()
  response.cookies.set("access_token", newAccessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    // No seteamos maxAge aquí — el backend ya definió la expiración en el JWT
  })

  return response
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
}
