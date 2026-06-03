import { type NextRequest, NextResponse } from "next/server"

const PUBLIC_PATHS = [
  "/login",
  "/forgot-password",
  "/reset-password",
  "/change-password",
]

function isTokenExpired(token: string): boolean {
  try {
    const parts = token.split(".")
    if (parts.length !== 3) return true
    // JWT usa base64url — normalizar a base64 antes de decodificar
    const base64 = parts[1]!.replace(/-/g, "+").replace(/_/g, "/")
    const payload = JSON.parse(atob(base64)) as { exp?: number }
    return typeof payload.exp !== "number" || payload.exp * 1000 < Date.now()
  } catch {
    return true
  }
}

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl

  const isPublic =
    PUBLIC_PATHS.some((p) => pathname.startsWith(p)) ||
    pathname.startsWith("/api/") ||
    pathname === "/"

  if (!isPublic) {
    const tokenCookie = request.cookies.get("access_token")
    if (!tokenCookie || isTokenExpired(tokenCookie.value)) {
      return NextResponse.redirect(new URL("/login", request.url))
    }
  }

  return NextResponse.next()
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
}
