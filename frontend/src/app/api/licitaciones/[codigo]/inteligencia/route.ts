import { cookies } from "next/headers"
import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"

const INTERNAL_API = process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

interface RouteParams {
  params: Promise<{ codigo: string }>
}

export async function GET(
  _request: NextRequest,
  { params }: RouteParams
): Promise<Response> {
  const { codigo } = await params
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value ?? null

  if (!accessToken) {
    return NextResponse.json({ detail: "Sin sesión" }, { status: 401 })
  }

  let backendResponse: Response
  try {
    backendResponse = await fetch(
      `${INTERNAL_API}/api/v1/licitaciones/${encodeURIComponent(codigo)}/inteligencia`,
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
      detail: "Error al obtener inteligencia",
    }))) as { detail?: string }
    return NextResponse.json(
      { detail: errorBody.detail ?? "Error al obtener inteligencia" },
      { status: backendResponse.status }
    )
  }

  const data: unknown = await backendResponse.json()
  return NextResponse.json(data)
}
