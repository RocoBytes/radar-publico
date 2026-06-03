/**
 * Route Handler proxy para el chat IA de una licitación.
 *
 * GET  /api/chat/[codigo] → proxy GET  /api/v1/chat/{codigo}         (historial)
 * POST /api/chat/[codigo] → proxy POST /api/v1/chat/{codigo}/mensaje (SSE stream)
 *
 * Lee el access_token de la cookie httpOnly y lo reenvía al backend
 * como Authorization: Bearer. El browser nunca ve el token.
 */

import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const INTERNAL_API =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

interface RouteParams {
  params: Promise<{ codigo: string }>
}

/** Lee el access_token de la cookie httpOnly. Retorna null si no existe. */
async function getAccessToken(): Promise<string | null> {
  const cookieStore = await cookies()
  return cookieStore.get("access_token")?.value ?? null
}

/** GET /api/chat/[codigo] — devuelve el historial de la conversación */
export async function GET(
  _request: NextRequest,
  { params }: RouteParams
): Promise<Response> {
  const { codigo } = await params

  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/chat/${encodeURIComponent(codigo)}`,
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        cache: "no-store",
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
      detail: "Error al obtener historial",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al obtener historial" },
      { status: backendResponse.status }
    )
  }

  const data: unknown = await backendResponse.json()
  return NextResponse.json(data)
}

/** POST /api/chat/[codigo] — envía un mensaje y hace pipe del SSE stream al browser */
export async function POST(
  request: NextRequest,
  { params }: RouteParams
): Promise<Response> {
  const { codigo } = await params

  const accessToken = await getAccessToken()
  if (!accessToken) {
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let body: unknown
  try {
    body = await request.json()
  } catch {
    return NextResponse.json(
      { detail: "Cuerpo de request inválido" },
      { status: 400 }
    )
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/chat/${encodeURIComponent(codigo)}/mensaje`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
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
      detail: "Error al enviar mensaje",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al enviar mensaje" },
      { status: backendResponse.status }
    )
  }

  if (!backendResponse.body) {
    return NextResponse.json({ detail: "Sin stream del backend" }, { status: 500 })
  }

  // Pipe directo del stream SSE del backend al browser
  return new Response(backendResponse.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no", // evita buffering en nginx/Caddy
    },
  })
}
