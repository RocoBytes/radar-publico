import { cookies } from "next/headers";
import type { CuentaResponse } from "@/types/admin";

const INTERNAL_API_URL =
  process.env["INTERNAL_API_URL"] ?? "http://localhost:8000";

/**
 * Lee el access_token de las cookies httpOnly y llama a /api/v1/auth/me.
 * Retorna el usuario si es admin, null en cualquier otro caso.
 * Solo para uso en Server Components.
 */
export async function getAdminUser(): Promise<CuentaResponse | null> {
  try {
    const cookieStore = await cookies();
    const accessToken = cookieStore.get("access_token");

    if (!accessToken?.value) {
      return null;
    }

    const res = await fetch(`${INTERNAL_API_URL}/api/v1/auth/me`, {
      headers: {
        Cookie: `access_token=${accessToken.value}`,
      },
      cache: "no-store",
    });

    if (!res.ok) {
      return null;
    }

    const user = (await res.json()) as CuentaResponse;

    if (user.rol !== "admin") {
      return null;
    }

    return user;
  } catch {
    return null;
  }
}
