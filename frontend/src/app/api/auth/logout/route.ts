/**
 * Route Handler proxy: POST /api/auth/logout
 *
 * Invalida el refresh token en el backend y limpia las cookies.
 */

import { cookies } from "next/headers"
import { NextResponse } from "next/server"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

export async function POST(): Promise<NextResponse> {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get("refresh_token")?.value
  const accessToken = cookieStore.get("access_token")?.value

  // Invalidar en el backend (best-effort: si falla igual limpiamos cookies)
  if (refreshToken) {
    try {
      await fetch(`${INTERNAL_API}/api/v1/auth/logout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
    } catch {
      // Ignorar error de red: igual limpiamos cookies locales
    }
  }

  const response = NextResponse.json({ ok: true })
  response.cookies.delete("access_token")
  response.cookies.delete("refresh_token")
  return response
}
