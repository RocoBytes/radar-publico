/**
 * Route Handler proxy: POST /api/auth/login
 *
 * Recibe credenciales del browser, las reenvía al backend interno,
 * y setea cookies httpOnly con los tokens devueltos.
 */

import { type NextRequest, NextResponse } from "next/server"
import type { LoginResponse } from "@/types/auth"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

const IS_PROD = process.env["NODE_ENV"] === "production"

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json({ detail: "Cuerpo de request inválido" }, { status: 400 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(`${INTERNAL_API}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  } catch {
    return NextResponse.json(
      { detail: "Error de conexión con el servidor" },
      { status: 502 }
    )
  }

  if (!backendResponse.ok) {
    const errorBody = (await backendResponse.json().catch(() => ({
      detail: "Error de autenticación",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error de autenticación" },
      { status: backendResponse.status }
    )
  }

  const data = (await backendResponse.json()) as LoginResponse

  const response = NextResponse.json({
    must_change_password: data.must_change_password,
  })

  // Cookie del access token: path "/" para que todos los Server Components lo lean
  response.cookies.set("access_token", data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: IS_PROD,
    path: "/",
    maxAge: 900, // 15 minutos
  })

  // Cookie del refresh token: path restringido al Route Handler de refresh
  response.cookies.set("refresh_token", data.refresh_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: IS_PROD,
    path: "/api/auth/refresh",
    maxAge: 604800, // 7 días
  })

  return response
}
