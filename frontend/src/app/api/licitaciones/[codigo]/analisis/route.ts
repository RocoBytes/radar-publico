import { cookies } from "next/headers"
import { NextResponse } from "next/server"
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
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/licitaciones/${encodeURIComponent(codigo)}/analisis`,
      {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        cache: "no-store",
      }
    )
  } catch {
    return NextResponse.json({ detail: "Error de conexión" }, { status: 502 })
  }

  if (!backendResponse.ok) {
    const errorBody = (await backendResponse.json().catch(() => ({
      detail: "Error al obtener el análisis",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al obtener el análisis" },
      { status: backendResponse.status }
    )
  }

  const data: unknown = await backendResponse.json()
  return NextResponse.json(data)
}

export async function POST(
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
      `${INTERNAL_API}/api/v1/licitaciones/${encodeURIComponent(codigo)}/analisis`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        cache: "no-store",
      }
    )
  } catch {
    return NextResponse.json({ detail: "Error de conexión" }, { status: 502 })
  }

  const body: unknown = await backendResponse.json().catch(() => ({}))
  return NextResponse.json(body, { status: backendResponse.status })
}
