import type {
  CuentaListResponse,
  CuentaResponse,
  CuentaCreadaResponse,
  CrearCuentaPayload,
  ImpersonacionResponse,
  TicketDiagnosticoResponse,
  TicketResponse,
} from "@/types/admin";
import type { AdminKpis, AdminCostosIaResponse } from "@/types/admin-kpis";

const BACKEND_URL =
  process.env["NEXT_PUBLIC_API_URL"] ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

// ─── Fetch base con interceptor de refresh ────────────────────────────────────

async function apiFetch<T>(
  url: string,
  options: RequestInit & { skipRefresh?: boolean } = {}
): Promise<T> {
  const { skipRefresh, ...fetchOptions } = options;

  const res = await fetch(url, {
    ...fetchOptions,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...fetchOptions.headers,
    },
  });

  if (res.status === 401 && !skipRefresh) {
    // Intentar refresh del token
    const refreshRes = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    });

    if (!refreshRes.ok) {
      // Refresh falló — redirigir a login
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Sesión expirada");
    }

    // Reintentar la request original
    const retryRes = await fetch(url, {
      ...fetchOptions,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...fetchOptions.headers,
      },
    });

    if (!retryRes.ok) {
      const errorData = (await retryRes.json().catch(() => ({}))) as {
        detail?: string;
      };
      throw new ApiError(
        retryRes.status,
        errorData.detail ?? `Error ${retryRes.status}`
      );
    }

    return retryRes.json() as Promise<T>;
  }

  if (!res.ok) {
    const errorData = (await res.json().catch(() => ({}))) as {
      detail?: string;
    };
    throw new ApiError(res.status, errorData.detail ?? `Error ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// ─── Auth helpers ─────────────────────────────────────────────────────────────

export async function authFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  return apiFetch<T>(`${BACKEND_URL}/api/v1/auth${path}`, options);
}

// ─── Admin helpers ────────────────────────────────────────────────────────────

async function adminFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  return apiFetch<T>(`${BACKEND_URL}/api/admin${path}`, options);
}

// ─── Endpoints de cuentas ────────────────────────────────────────────────────

export async function getCuentas(page = 1): Promise<CuentaListResponse> {
  return adminFetch<CuentaListResponse>(
    `/cuentas?page=${page}&page_size=25`
  );
}

export async function crearCuenta(
  data: CrearCuentaPayload
): Promise<CuentaCreadaResponse> {
  return adminFetch<CuentaCreadaResponse>("/cuentas", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function obtenerCuenta(id: string): Promise<CuentaResponse> {
  return adminFetch<CuentaResponse>(`/cuentas/${id}`);
}

export async function cambiarEstado(
  id: string,
  accion: "reactivar" | "suspender"
): Promise<CuentaResponse> {
  return adminFetch<CuentaResponse>(`/cuentas/${id}/estado`, {
    method: "PATCH",
    body: JSON.stringify({ accion }),
  });
}

export async function cargarTicket(
  id: string,
  ticket: string
): Promise<TicketResponse> {
  return adminFetch<TicketResponse>(`/cuentas/${id}/ticket`, {
    method: "POST",
    body: JSON.stringify({ ticket }),
  });
}

export async function impersonarCuenta(id: string): Promise<ImpersonacionResponse> {
  return adminFetch<ImpersonacionResponse>(`/cuentas/${id}/impersonar`, {
    method: "POST",
  });
}

export async function diagnosticarTicket(
  id: string,
  testConexion = false
): Promise<TicketDiagnosticoResponse> {
  const qs = testConexion ? "?test_conexion=true" : "";
  return adminFetch<TicketDiagnosticoResponse>(`/cuentas/${id}/ticket/diagnostico${qs}`);
}

// ─── Endpoints de dashboard ──────────────────────────────────────────────────

export async function getAdminKpis(): Promise<AdminKpis> {
  return adminFetch<AdminKpis>("/dashboard/kpis");
}

export async function getAdminCostosIa(
  meses: number = 1
): Promise<AdminCostosIaResponse> {
  return adminFetch<AdminCostosIaResponse>(
    `/dashboard/costos-ia?meses=${meses}`
  );
}
