import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  // Reenviar las cookies de la request al backend
  const cookieHeader = req.headers.get("cookie") ?? "";

  const backendRes = await fetch(`${INTERNAL_API_URL}/api/v1/auth/refresh`, {
    method: "POST",
    headers: {
      Cookie: cookieHeader,
    },
  });

  const data: unknown = await backendRes.json().catch(() => ({}));

  const res = NextResponse.json(data, { status: backendRes.status });

  // Copiar Set-Cookie del backend
  const setCookie = backendRes.headers.get("set-cookie");
  if (setCookie) {
    res.headers.set("set-cookie", setCookie);
  }

  return res;
}
