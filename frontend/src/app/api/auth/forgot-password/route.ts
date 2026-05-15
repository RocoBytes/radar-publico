/**
 * Route Handler proxy: POST /api/auth/forgot-password
 *
 * Reenvía el email al backend. Siempre retorna 204 (anti-enumeración):
 * el backend nunca revela si el email existe o no.
 */

import { type NextRequest, NextResponse } from "next/server"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

export async function POST(request: NextRequest): Promise<NextResponse> {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return new NextResponse(null, { status: 400 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/auth/forgot-password`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }
    )
  } catch {
    return new NextResponse(null, { status: 502 })
  }

  return new NextResponse(null, { status: backendResponse.status })
}
