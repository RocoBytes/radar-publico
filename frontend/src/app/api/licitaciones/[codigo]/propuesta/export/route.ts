import { cookies } from "next/headers"
import type { NextRequest } from "next/server"

const INTERNAL_API = process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

interface RouteParams {
  params: Promise<{ codigo: string }>
}

async function getAccessToken(): Promise<string | null> {
  const cookieStore = await cookies()
  return cookieStore.get("access_token")?.value ?? null
}

export async function GET(
  _request: NextRequest,
  { params }: RouteParams
): Promise<Response> {
  const { codigo } = await params
  const accessToken = await getAccessToken()

  if (!accessToken) {
    return new Response(JSON.stringify({ detail: "Sin sesión" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/licitaciones/${encodeURIComponent(codigo)}/propuesta/export`,
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      }
    )
  } catch {
    return new Response(JSON.stringify({ detail: "Error de conexión" }), {
      status: 502,
      headers: { "Content-Type": "application/json" },
    })
  }

  if (!backendResponse.ok) {
    return new Response(JSON.stringify({ detail: "Error al exportar el borrador" }), {
      status: backendResponse.status,
      headers: { "Content-Type": "application/json" },
    })
  }

  // Pasar el binario y los headers de descarga tal como vienen del backend
  const buffer = await backendResponse.arrayBuffer()
  return new Response(buffer, {
    headers: {
      "Content-Type":
        backendResponse.headers.get("content-type") ??
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "Content-Disposition":
        backendResponse.headers.get("content-disposition") ??
        `attachment; filename="propuesta-${codigo}.docx"`,
    },
  })
}
