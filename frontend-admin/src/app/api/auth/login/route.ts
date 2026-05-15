import { NextRequest, NextResponse } from "next/server";

const INTERNAL_API_URL =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000";

export async function POST(req: NextRequest): Promise<NextResponse> {
  const body = await req.text();

  const backendRes = await fetch(`${INTERNAL_API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body,
  });

  const data: unknown = await backendRes.json().catch(() => ({}));

  const res = NextResponse.json(data, { status: backendRes.status });

  // Copiar Set-Cookie del backend al response del Route Handler
  const setCookie = backendRes.headers.get("set-cookie");
  if (setCookie) {
    res.headers.set("set-cookie", setCookie);
  }

  return res;
}
