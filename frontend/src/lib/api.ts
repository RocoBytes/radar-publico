/**
 * Cliente HTTP tipado para la API de Radar Público.
 *
 * Estrategia de fetch:
 * - Desde el browser: llama a /api/auth/* (Route Handlers proxy, mismo origen).
 *   Para endpoints de datos llama al backend directamente con cookies.
 * - Desde Server Components: llama directamente al backend interno.
 *
 * Interceptor de refresh (client-side):
 * - Ante 401, intenta POST /api/auth/refresh UNA vez.
 * - Si el refresh tiene éxito, reintenta el request original.
 * - Si el refresh falla, redirige a /login.
 */

import type { UserMe } from "@/types/auth"
import type { Notificacion, NotificacionesResumen } from "@/types/notificacion"
import type { DashboardResumen, DashboardSegmentos } from "@/types/dashboard"
import type {
  AnalisisBases,
  BorradorPropuesta,
  LicitacionListResponse,
  LicitacionDetalle,
  LicitacionFiltros,
} from "@/types/licitacion"
import type {
  PipelineListResponse,
  PipelineItemDetail,
  PipelineItemUpdateRequest,
  PipelineItemCreateRequest,
  PipelineNota,
} from "@/types/pipeline"
import type {
  RadarListResponse,
  Radar,
  RadarCreateRequest,
  RadarUpdateRequest,
} from "@/types/radar"
import type { Conversacion, Cita, SseEvent } from "@/types/chat"
import type { EmpresaProfile, EmpresaUpdateRequest } from "@/types/empresa"
import type {
  PreferenciasNotificaciones,
  PreferenciasUpdateRequest,
} from "@/types/preferencias"
import type { OrganismosResponse, ProveedoresResponse } from "@/types/directorios"
import type { TendenciaResponse, TopOrganismosResponse } from "@/types/analytics"
import type { InadmisibilidadData, InteligenciaData } from "@/types/inteligencia"
import type {
  CatalogosRegionesResponse,
  CatalogosUnspscResponse,
} from "@/types/catalogos"
import type {
  Interes,
  InteresCreateRequest,
  InteresListResponse,
} from "@/types/intereses"
import type {
  ChecklistItem,
  ChecklistItemCreateRequest,
  ChecklistItemUpdateRequest,
  ChecklistBootstrapResponse,
} from "@/types/checklist"

// URL pública del backend (usada en client components cuando llaman directo al backend)
// Para SSR se usa INTERNAL_API_URL desde los Server Components / Route Handlers
const BACKEND_URL =
  process.env["NEXT_PUBLIC_API_URL"] ?? "http://localhost:8000"

// Prefijo de la API del backend
const API_PREFIX = "/api/v1"

/** Error tipado de la API */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(detail)
    this.name = "ApiError"
  }
}

/** Opciones extendidas para apiFetch */
interface FetchOptions extends RequestInit {
  /** Si true, no intenta refresh automático ante 401 (evitar recursión) */
  skipRefresh?: boolean
}

/**
 * Fetch wrapper client-side que apunta a los Route Handlers proxy.
 * Incluye interceptor de refresh ante 401.
 * Usar en Client Components y hooks de TanStack Query.
 */
export async function apiFetch<T>(
  path: string,
  options: FetchOptions = {}
): Promise<T> {
  const { skipRefresh = false, ...init } = options

  const response = await fetch(`${BACKEND_URL}${API_PREFIX}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
    credentials: "include",
  })

  if (response.status === 401 && !skipRefresh) {
    // Intento de refresh token UNA vez
    const refreshed = await attemptRefresh()
    if (refreshed) {
      // Reintento del request original sin interceptor para evitar bucle
      return apiFetch<T>(path, { ...options, skipRefresh: true })
    }
    // Refresh falló: redirigir a login
    if (typeof window !== "undefined") {
      window.location.href = "/login"
    }
    throw new ApiError(401, "Sesión expirada")
  }

  if (!response.ok) {
    let detail = `Error ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Ignorar error de parseo
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

/**
 * Intenta refrescar la sesión llamando al Route Handler proxy de refresh.
 * Devuelve true si el refresh fue exitoso.
 */
async function attemptRefresh(): Promise<boolean> {
  try {
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      credentials: "include",
    })
    return response.ok
  } catch {
    return false
  }
}

/**
 * Fetch server-side para Server Components y Route Handlers.
 * Llama directamente al backend interno sin interceptor de refresh.
 * El token se pasa explícitamente como parámetro.
 */
export async function serverFetch<T>(
  path: string,
  accessToken: string,
  options: RequestInit = {}
): Promise<T> {
  const internalUrl =
    process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"

  const response = await fetch(`${internalUrl}${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
      ...options.headers,
    },
    // Sin credentials: el token viene explícito
    cache: "no-store",
  })

  if (!response.ok) {
    let detail = `Error ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // Ignorar error de parseo
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

// --- Funciones de API tipadas ---

/** Obtiene el perfil del usuario autenticado (server-side). */
export async function getMe(accessToken: string): Promise<UserMe> {
  return serverFetch<UserMe>("/auth/me", accessToken)
}

/** Obtiene el perfil del usuario autenticado (client-side, con cookies). */
export async function getMeClient(): Promise<UserMe> {
  return apiFetch<UserMe>("/auth/me")
}

// ---- Dashboard ----

export async function getDashboardResumen(): Promise<DashboardResumen> {
  return apiFetch<DashboardResumen>("/dashboard/resumen")
}

export async function getDashboardSegmentos(
  soloIntereses = false
): Promise<DashboardSegmentos> {
  return apiFetch<DashboardSegmentos>(
    `/dashboard/segmentos?solo_intereses=${soloIntereses}`
  )
}

// ---- Licitaciones ----

export async function getLicitaciones(
  filtros: LicitacionFiltros = {}
): Promise<LicitacionListResponse> {
  const params = new URLSearchParams()
  Object.entries(filtros).forEach(([k, v]) => {
    if (v !== undefined) params.set(k, String(v))
  })
  return apiFetch<LicitacionListResponse>(`/licitaciones?${params}`)
}

export async function getLicitacion(codigo: string): Promise<LicitacionDetalle> {
  return apiFetch<LicitacionDetalle>(
    `/licitaciones/${encodeURIComponent(codigo)}`
  )
}

// ---- Pipeline ----

export async function getPipeline(
  params: {
    estado?: string
    licitacion_codigo?: string
    page?: number
    page_size?: number
  } = {}
): Promise<PipelineListResponse> {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined) q.set(k, String(v))
  })
  return apiFetch<PipelineListResponse>(`/pipeline?${q}`)
}

export async function getPipelineItem(id: string): Promise<PipelineItemDetail> {
  return apiFetch<PipelineItemDetail>(`/pipeline/${id}`)
}

export async function createPipelineItem(
  data: PipelineItemCreateRequest
): Promise<PipelineItemDetail> {
  return apiFetch<PipelineItemDetail>("/pipeline", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updatePipelineItem(
  id: string,
  data: PipelineItemUpdateRequest
): Promise<PipelineItemDetail> {
  return apiFetch<PipelineItemDetail>(`/pipeline/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export async function createPipelineNota(
  itemId: string,
  contenido: string
): Promise<PipelineNota> {
  return apiFetch<PipelineNota>(`/pipeline/${itemId}/notas`, {
    method: "POST",
    body: JSON.stringify({ contenido }),
  })
}

export async function deletePipelineNota(
  itemId: string,
  notaId: string
): Promise<void> {
  return apiFetch<void>(`/pipeline/${itemId}/notas/${notaId}`, {
    method: "DELETE",
  })
}

// ---- Radares ----

export async function getRadares(): Promise<RadarListResponse> {
  return apiFetch<RadarListResponse>("/radares")
}

export async function createRadar(data: RadarCreateRequest): Promise<Radar> {
  return apiFetch<Radar>("/radares", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updateRadar(
  id: string,
  data: RadarUpdateRequest
): Promise<Radar> {
  return apiFetch<Radar>(`/radares/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

export async function deleteRadar(id: string): Promise<void> {
  return apiFetch<void>(`/radares/${id}`, { method: "DELETE" })
}

// ---- Notificaciones ----

export async function getNotificacionesResumen(): Promise<NotificacionesResumen> {
  return apiFetch<NotificacionesResumen>("/notificaciones/resumen")
}

export async function marcarNotificacionLeida(id: string): Promise<Notificacion> {
  return apiFetch<Notificacion>(`/notificaciones/${id}/leer`, {
    method: "POST",
  })
}

// ---- Chat IA ----

/**
 * Obtiene el historial de la conversación de una licitación.
 * Llama al Route Handler /api/chat/[codigo] que gestiona la auth con cookie httpOnly.
 */
export async function getChatHistorial(codigo: string): Promise<Conversacion> {
  const res = await fetch(`/api/chat/${encodeURIComponent(codigo)}`, {
    credentials: "include",
    cache: "no-store",
  })
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al cargar historial"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<Conversacion>
}

/**
 * Envía un mensaje al asistente IA y consume el stream SSE.
 * Llama al Route Handler /api/chat/[codigo] que gestiona la auth con cookie httpOnly.
 *
 * Los callbacks se invocan conforme llegan los eventos:
 * - onDelta: fragmento de texto generado
 * - onCitas: citas de las bases al terminar
 * - onFin:   mensaje_id cuando el stream cierra
 * - onError: detalle del error (incluye rate limit 429)
 */
export async function streamChatMensaje(
  codigo: string,
  contenido: string,
  onDelta: (texto: string) => void,
  onCitas: (citas: Cita[]) => void,
  onFin: (mensajeId: string) => void,
  onError: (detail: string) => void
): Promise<void> {
  const res = await fetch(`/api/chat/${encodeURIComponent(codigo)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ contenido }),
  })

  if (!res.ok) {
    const body = (await res.json().catch(() => ({ detail: "Error" }))) as {
      detail?: string
    }
    onError(body.detail ?? "Error al enviar mensaje")
    return
  }

  if (!res.body) {
    onError("Sin stream del servidor")
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split("\n")
      buffer = lines.pop() ?? ""

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue
        try {
          const event = JSON.parse(line.slice(6)) as SseEvent
          if (event.tipo === "delta") onDelta(event.texto)
          else if (event.tipo === "citas") onCitas(event.citas)
          else if (event.tipo === "fin") onFin(event.mensaje_id)
          else if (event.tipo === "error") onError(event.detail)
        } catch {
          // Ignorar líneas no parseables (keep-alive, comentarios SSE)
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// ---- Empresa (configuración) ----

export async function getEmpresaMe(): Promise<EmpresaProfile> {
  return apiFetch<EmpresaProfile>("/empresa/me")
}

/** Obtiene el perfil de empresa del usuario autenticado (server-side). */
export async function getEmpresa(accessToken: string): Promise<EmpresaProfile> {
  return serverFetch<EmpresaProfile>("/empresa/me", accessToken)
}

export async function updateEmpresaMe(
  data: EmpresaUpdateRequest
): Promise<EmpresaProfile> {
  return apiFetch<EmpresaProfile>("/empresa/me", {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

// ---- Catálogos (sin autenticación) ----

export async function getCatalogosRegiones(): Promise<CatalogosRegionesResponse> {
  return apiFetch<CatalogosRegionesResponse>("/catalogos/regiones")
}

export async function getCatalogosUnspsc(): Promise<CatalogosUnspscResponse> {
  return apiFetch<CatalogosUnspscResponse>("/catalogos/unspsc")
}

export async function triggerSyncLicitaciones(): Promise<{ status: string; message: string }> {
  return apiFetch<{ status: string; message: string }>("/sync/licitaciones", { method: "POST" })
}

// ---- Intereses ----

export async function getIntereses(): Promise<InteresListResponse> {
  return apiFetch<InteresListResponse>("/intereses")
}

export async function createInteres(data: InteresCreateRequest): Promise<Interes> {
  return apiFetch<Interes>("/intereses", {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function deleteInteres(id: string): Promise<void> {
  return apiFetch<void>(`/intereses/${id}`, { method: "DELETE" })
}

export async function submitTicketRequest(
  ticket_texto: string
): Promise<{ mensaje: string }> {
  return apiFetch<{ mensaje: string }>("/empresa/ticket-request", {
    method: "POST",
    body: JSON.stringify({ ticket_texto }),
  })
}

// ---- Preferencias de notificaciones ----

export async function getPreferencias(): Promise<PreferenciasNotificaciones> {
  return apiFetch<PreferenciasNotificaciones>("/preferencias-notificaciones")
}

export async function updatePreferencias(
  data: PreferenciasUpdateRequest
): Promise<PreferenciasNotificaciones> {
  return apiFetch<PreferenciasNotificaciones>("/preferencias-notificaciones", {
    method: "PATCH",
    body: JSON.stringify(data),
  })
}

// ---- Analytics ----

export async function getDashboardTendencia(
  meses = 12
): Promise<TendenciaResponse> {
  return apiFetch<TendenciaResponse>(`/dashboard/tendencia?meses=${meses}`)
}

export async function getDashboardTopOrganismos(
  top = 10,
  meses = 12
): Promise<TopOrganismosResponse> {
  return apiFetch<TopOrganismosResponse>(
    `/dashboard/top-organismos?top=${top}&meses=${meses}`
  )
}

// ---- Análisis IA de bases ----

/**
 * Obtiene el análisis IA de las bases técnicas de una licitación.
 * Lanza ApiError con status 404 si todavía no hay análisis disponible.
 */
export async function getAnalisisBases(codigo: string): Promise<AnalisisBases> {
  const res = await fetch(
    `/api/licitaciones/${encodeURIComponent(codigo)}/analisis`,
    { credentials: "include", cache: "no-store" }
  )
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al obtener el análisis"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<AnalisisBases>
}

/**
 * Solicita el análisis IA de las bases técnicas de una licitación.
 * El análisis se procesa en background — consultar con getAnalisisBases() para el resultado.
 */
export async function triggerAnalisisBases(
  codigo: string
): Promise<{ status: string; mensaje: string }> {
  const res = await fetch(
    `/api/licitaciones/${encodeURIComponent(codigo)}/analisis`,
    { method: "POST", credentials: "include", cache: "no-store" }
  )
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al solicitar el análisis"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<{ status: string; mensaje: string }>
}

// ---- Propuesta técnica (Módulo 2) ----

/**
 * Obtiene el borrador de propuesta técnica generado para la empresa del usuario.
 * Lanza ApiError con status 404 si todavía no hay borrador disponible.
 */
export async function getBorradorPropuesta(codigo: string): Promise<BorradorPropuesta> {
  const res = await fetch(
    `/api/licitaciones/${encodeURIComponent(codigo)}/propuesta`,
    { credentials: "include", cache: "no-store" }
  )
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al obtener el borrador"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<BorradorPropuesta>
}

/**
 * Solicita la generación del borrador de propuesta técnica.
 * Requiere que el análisis de bases esté en status='listo'.
 */
export async function triggerBorradorPropuesta(
  codigo: string
): Promise<{ status: string; mensaje: string }> {
  const res = await fetch(
    `/api/licitaciones/${encodeURIComponent(codigo)}/propuesta`,
    { method: "POST", credentials: "include", cache: "no-store" }
  )
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al generar el borrador"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<{ status: string; mensaje: string }>
}

// ---- Inteligencia ----

/**
 * Obtiene datos de inteligencia comercial de una licitación.
 * Llama al Route Handler /api/licitaciones/[codigo]/inteligencia que gestiona la auth con cookie httpOnly.
 */
export async function getLicitacionInteligencia(
  codigo: string
): Promise<InteligenciaData> {
  const res = await fetch(
    `/api/licitaciones/${encodeURIComponent(codigo)}/inteligencia`,
    {
      credentials: "include",
      cache: "no-store",
    }
  )
  if (res.status === 401) throw new ApiError(401, "Sesión expirada")
  if (!res.ok) {
    let detail = "Error al obtener inteligencia"
    try {
      const body = (await res.json()) as { detail?: string }
      if (body.detail) detail = body.detail
    } catch {
      // ignorar
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<InteligenciaData>
}

export async function getInadmisibilidad(
  codigo: string
): Promise<InadmisibilidadData> {
  return apiFetch<InadmisibilidadData>(
    `/licitaciones/${encodeURIComponent(codigo)}/inadmisibilidad`
  )
}

export async function getOrganismos(params: {
  q?: string
  region?: string
  page?: number
  page_size?: number
}): Promise<OrganismosResponse> {
  const q = new URLSearchParams()
  if (params.q) q.set("q", params.q)
  if (params.region) q.set("region", params.region)
  if (params.page) q.set("page", String(params.page))
  if (params.page_size) q.set("page_size", String(params.page_size))
  return apiFetch<OrganismosResponse>(`/directorios/organismos?${q}`)
}

export async function getProveedores(params: {
  q?: string
  page?: number
  page_size?: number
}): Promise<ProveedoresResponse> {
  const q = new URLSearchParams()
  if (params.q) q.set("q", params.q)
  if (params.page) q.set("page", String(params.page))
  if (params.page_size) q.set("page_size", String(params.page_size))
  return apiFetch<ProveedoresResponse>(`/directorios/proveedores?${q}`)
}

// ---- Checklist documental ----

export async function getChecklist(
  pipelineItemId: string,
  params?: { limit?: number; offset?: number }
): Promise<ChecklistItem[]> {
  const q = new URLSearchParams()
  if (params?.limit !== undefined) q.set("limit", String(params.limit))
  if (params?.offset !== undefined) q.set("offset", String(params.offset))
  const qs = q.toString() ? `?${q}` : ""
  return apiFetch<ChecklistItem[]>(`/pipeline/${pipelineItemId}/checklist${qs}`)
}

export async function createChecklistItem(
  pipelineItemId: string,
  data: ChecklistItemCreateRequest
): Promise<ChecklistItem> {
  return apiFetch<ChecklistItem>(`/pipeline/${pipelineItemId}/checklist`, {
    method: "POST",
    body: JSON.stringify(data),
  })
}

export async function updateChecklistItem(
  pipelineItemId: string,
  itemId: string,
  data: ChecklistItemUpdateRequest
): Promise<ChecklistItem> {
  return apiFetch<ChecklistItem>(
    `/pipeline/${pipelineItemId}/checklist/${itemId}`,
    { method: "PATCH", body: JSON.stringify(data) }
  )
}

export async function deleteChecklistItem(
  pipelineItemId: string,
  itemId: string
): Promise<void> {
  return apiFetch<void>(`/pipeline/${pipelineItemId}/checklist/${itemId}`, {
    method: "DELETE",
  })
}

export async function bootstrapChecklist(
  pipelineItemId: string
): Promise<ChecklistBootstrapResponse> {
  return apiFetch<ChecklistBootstrapResponse>(
    `/pipeline/${pipelineItemId}/checklist/bootstrap-from-analysis`,
    { method: "POST" }
  )
}
