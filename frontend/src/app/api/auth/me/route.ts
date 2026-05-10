/**
 * Route Handler proxy: GET /api/auth/me
 *
 * Usado por Server Components para obtener el usuario actual.
 * Lee el access_token de las cookies y lo reenvía al backend.
 */

import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { UserMe } from "@/types/auth"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

export async function GET(): Promise<NextResponse> {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value

  if (!accessToken) {
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(`${INTERNAL_API}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    })
  } catch {
    return NextResponse.json({ detail: "Error de conexión" }, { status: 502 })
  }

  if (!backendResponse.ok) {
    return NextResponse.json(
      { detail: "Sesión inválida" },
      { status: backendResponse.status }
    )
  }

  const user = (await backendResponse.json()) as UserMe
  return NextResponse.json(user)
}
