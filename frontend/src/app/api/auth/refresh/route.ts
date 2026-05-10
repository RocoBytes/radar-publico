/**
 * Route Handler proxy: POST /api/auth/refresh
 *
 * Invocable desde:
 * - Browser: interceptor TanStack Query ante 401
 * - Server Components: accediendo a cookies() de next/headers
 *
 * Lee el refresh_token de la cookie httpOnly,
 * lo reenvía al backend y rota ambas cookies.
 */

import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { RefreshResponse } from "@/types/auth"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

const IS_PROD = process.env["NODE_ENV"] === "production"

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get("refresh_token")?.value

  if (!refreshToken) {
    return NextResponse.json({ detail: "Sin refresh token" }, { status: 401 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(`${INTERNAL_API}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
  } catch {
    return NextResponse.json(
      { detail: "Error de conexión con el servidor" },
      { status: 502 }
    )
  }

  if (!backendResponse.ok) {
    // Refresh inválido: limpiar ambas cookies
    const response = NextResponse.json(
      { detail: "Sesión expirada" },
      { status: 401 }
    )
    response.cookies.delete("access_token")
    response.cookies.delete("refresh_token")
    return response
  }

  const data = (await backendResponse.json()) as RefreshResponse

  const response = NextResponse.json({ ok: true })

  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: IS_PROD,
    path: "/",
    maxAge: 900,
  })

  response.cookies.set("refresh_token", data.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: IS_PROD,
    path: "/api/auth/refresh",
    maxAge: 604800,
  })

  return response
}
