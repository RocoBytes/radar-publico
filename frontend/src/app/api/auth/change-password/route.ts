/**
 * Route Handler proxy: POST /api/auth/change-password
 *
 * Reenvía la solicitud al backend con el access_token de la cookie.
 * El backend también lee el refresh_token desde Cookie header para preservar la sesión actual.
 */

import { cookies } from "next/headers"
import { type NextRequest, NextResponse } from "next/server"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

export async function POST(request: NextRequest): Promise<NextResponse> {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value
  const refreshToken = cookieStore.get("refresh_token")?.value

  if (!accessToken) {
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ detail: "Cuerpo de request inválido" }, { status: 400 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(`${INTERNAL_API}/api/v1/auth/change-password`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
        // Pasar el refresh token como Cookie para que el backend lo preserve
        ...(refreshToken ? { Cookie: `refresh_token=${refreshToken}` } : {}),
      },
      body: JSON.stringify(body),
    })
  } catch {
    return NextResponse.json({ detail: "Error de conexión" }, { status: 502 })
  }

  if (!backendResponse.ok) {
    const errorBody = (await backendResponse.json().catch(() => ({
      detail: "Error al cambiar contraseña",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al cambiar contraseña" },
      { status: backendResponse.status }
    )
  }

  return NextResponse.json({ ok: true })
}
