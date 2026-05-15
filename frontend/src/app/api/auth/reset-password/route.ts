/**
 * Route Handler proxy: POST /api/auth/reset-password
 *
 * Reenvía el token y la nueva contraseña al backend.
 * Retorna 204 si OK, o el JSON de error del backend si falla (ej: 422).
 */

import { type NextRequest, NextResponse } from "next/server"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ detail: "Cuerpo de request inválido" }, { status: 400 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/auth/reset-password`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    )
  } catch {
    return NextResponse.json(
      { detail: "Error de conexión con el servidor" },
      { status: 502 }
    )
  }

  if (!backendResponse.ok) {
    const errorBody = (await backendResponse.json().catch(() => ({
      detail: "Error al restablecer la contraseña",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al restablecer la contraseña" },
      { status: backendResponse.status }
    )
  }

  return new NextResponse(null, { status: 204 })
}
