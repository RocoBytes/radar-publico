"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { differenceInCalendarDays, format, formatDistanceToNow, startOfDay } from "date-fns"
import { es } from "date-fns/locale"
import { Download, Loader2, RefreshCw, Search } from "lucide-react"
import { toast } from "sonner"
import { getCatalogosUnspsc, getLicitaciones, triggerSyncLicitaciones } from "@/lib/api"
import { downloadCsv } from "@/lib/csv"
import type { LicitacionEstado, LicitacionFiltros } from "@/types/licitacion"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

const ESTADOS_LICITACION: { value: LicitacionEstado; label: string }[] = [
  { value: "publicada", label: "Publicada" },
  { value: "cerrada", label: "Cerrada" },
  { value: "adjudicada", label: "Adjudicada" },
  { value: "desierta", label: "Desierta" },
  { value: "revocada", label: "Revocada" },
  { value: "suspendida", label: "Suspendida" },
]

const BADGE_VARIANTE: Record<LicitacionEstado, string> = {
  publicada: "bg-green-100 text-green-800 border-green-200",
  cerrada: "bg-yellow-100 text-yellow-800 border-yellow-200",
  adjudicada: "bg-blue-100 text-blue-800 border-blue-200",
  desierta: "bg-slate-100 text-slate-600 border-slate-200",
  revocada: "bg-slate-100 text-slate-600 border-slate-200",
  suspendida: "bg-slate-100 text-slate-600 border-slate-200",
}

function EstadoBadge({ estado }: { estado: LicitacionEstado }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE_VARIANTE[estado]}`}
    >
      {estado.charAt(0).toUpperCase() + estado.slice(1)}
    </span>
  )
}

function formatMontoCLP(monto: number | null): string {
  if (monto === null) return "—"
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(monto)
}

function formatFecha(fecha: string | null): string {
  if (!fecha) return "—"
  try {
    return format(new Date(fecha), "dd/MM/yyyy", { locale: es })
  } catch {
    return "—"
  }
}

type UrgenciaCierre = "urgente" | "pronto" | null

function urgenciaCierre(fecha: string | null, estado: LicitacionEstado): UrgenciaCierre {
  if (!fecha || estado !== "publicada") return null
  try {
    const dias = differenceInCalendarDays(new Date(fecha), startOfDay(new Date()))
    if (dias <= 1) return "urgente"
    if (dias <= 3) return "pronto"
  } catch {
    return null
  }
  return null
}

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 8 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-4 w-48" /></TableCell>
          <TableCell><Skeleton className="h-4 w-32" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
        </TableRow>
      ))}
    </>
  )
}

export function LicitacionesListClient() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const queryClient = useQueryClient()

  const [q, setQ] = useState(searchParams.get("q") ?? "")
  const [estado, setEstado] = useState<LicitacionEstado | "todos">(
    (searchParams.get("estado") as LicitacionEstado) ?? "todos"
  )
  const [unspsc, setUnspsc] = useState(searchParams.get("unspsc") ?? "")
  const [page, setPage] = useState(Number(searchParams.get("page") ?? "1"))
  const [debouncedQ, setDebouncedQ] = useState(q)
  const [exportando, setExportando] = useState(false)
  const [ultimaActualizacion, setUltimaActualizacion] = useState<Date | null>(null)
  const [syncCooldownUntil, setSyncCooldownUntil] = useState<Date | null>(null)

  const syncCooldownActivo = syncCooldownUntil != null && new Date() < syncCooldownUntil

  // Debounce búsqueda 300ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQ(q)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [q])

  // Sincronizar filtros a URL
  const syncUrl = useCallback(
    (nextQ: string, nextEstado: string, nextUnspsc: string, nextPage: number) => {
      const params = new URLSearchParams()
      if (nextQ) params.set("q", nextQ)
      if (nextEstado && nextEstado !== "todos") params.set("estado", nextEstado)
      if (nextUnspsc) params.set("unspsc", nextUnspsc)
      if (nextPage > 1) params.set("page", String(nextPage))
      const query = params.toString()
      router.replace(`/licitaciones${query ? `?${query}` : ""}`, { scroll: false })
    },
    [router]
  )

  useEffect(() => {
    syncUrl(debouncedQ, estado, unspsc, page)
  }, [debouncedQ, estado, unspsc, page, syncUrl])

  const filtros: LicitacionFiltros = {
    ...(debouncedQ ? { q: debouncedQ } : {}),
    ...(estado !== "todos" ? { estado } : {}),
    ...(unspsc ? { unspsc_codigo: unspsc } : {}),
    page,
    page_size: 25,
  }

  const { data, isLoading } = useQuery({
    queryKey: ["licitaciones", filtros],
    queryFn: () => getLicitaciones(filtros),
  })

  // Registrar cuándo se actualizaron los datos por última vez
  useEffect(() => {
    if (data) setUltimaActualizacion(new Date())
  }, [data])

  // Catálogo UNSPSC — se cachea 24h, no cambia en runtime
  const { data: catalogosUnspsc } = useQuery({
    queryKey: ["catalogos", "unspsc"],
    queryFn: getCatalogosUnspsc,
    staleTime: 24 * 60 * 60 * 1000,
  })

  const { mutate: dispararSync, isPending: sincronizando } = useMutation({
    mutationFn: triggerSyncLicitaciones,
    onSuccess: () => {
      toast.success("Sincronización iniciada — los resultados llegarán en ~1 minuto.")
      const cooldownFin = new Date(Date.now() + 90_000)
      setSyncCooldownUntil(cooldownFin)
      setTimeout(() => {
        void queryClient.invalidateQueries({ queryKey: ["licitaciones"] })
      }, 90_000)
    },
    onError: () => toast.error("No se pudo iniciar la sincronización. Intentá de nuevo."),
  })

  const hasNextPage = (data?.items.length ?? 0) >= 25
  const hasPrevPage = page > 1

  async function handleExport() {
    setExportando(true)
    try {
      const resultado = await getLicitaciones({ ...filtros, page: 1, page_size: 100 })
      const headers = ["Código", "Nombre", "Organismo", "Estado", "Monto Estimado (CLP)", "Fecha Publicación", "Fecha Cierre"]
      const rows = resultado.items.map((item) => [
        item.codigo,
        item.nombre,
        item.organismo_nombre ?? "",
        item.estado,
        item.monto_estimado,
        item.fecha_publicacion ? format(new Date(item.fecha_publicacion), "dd/MM/yyyy", { locale: es }) : "",
        item.fecha_cierre ? format(new Date(item.fecha_cierre), "dd/MM/yyyy", { locale: es }) : "",
      ])
      const fecha = format(new Date(), "yyyyMMdd")
      downloadCsv(`licitaciones-${fecha}`, headers, rows)
    } finally {
      setExportando(false)
    }
  }

  return (
    <div className="space-y-4">
      {/* Filtros — fila 1: búsqueda + estado + acciones */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Buscar licitaciones..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={estado}
          onValueChange={(val: string) => {
            setEstado(val as LicitacionEstado | "todos")
            setPage(1)
          }}
        >
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos los estados</SelectItem>
            {ESTADOS_LICITACION.map((e) => (
              <SelectItem key={e.value} value={e.value}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void handleExport()}
          disabled={exportando || isLoading || !data?.items.length}
          className="shrink-0"
        >
          {exportando ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Download className="mr-2 h-4 w-4" />
          )}
          {exportando ? "Exportando..." : "Exportar CSV"}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => dispararSync()}
          disabled={sincronizando || syncCooldownActivo}
          className="shrink-0"
          title="Consultar nuevas licitaciones desde ChileCompra"
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${sincronizando || syncCooldownActivo ? "animate-spin" : ""}`}
          />
          {sincronizando || syncCooldownActivo ? "Actualizando..." : "Actualizar"}
        </Button>
      </div>

      {/* Filtros — fila 2: rubro + meta de actualización */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Select
          value={unspsc || "todos"}
          onValueChange={(val) => {
            setUnspsc(val === "todos" ? "" : val)
            setPage(1)
          }}
        >
          <SelectTrigger className="w-full sm:w-72">
            <SelectValue placeholder="Todos los rubros" />
          </SelectTrigger>
          <SelectContent className="max-h-72">
            <SelectItem value="todos">Todos los rubros</SelectItem>
            {catalogosUnspsc?.items.map((seg) => (
              <SelectGroup key={seg.codigo}>
                <SelectLabel className="text-xs text-muted-foreground">
                  {seg.codigo} — {seg.nombre}
                </SelectLabel>
                <SelectItem value={seg.codigo} className="font-medium">
                  {seg.nombre}
                </SelectItem>
                {seg.familias.map((fam) => (
                  <SelectItem
                    key={fam.codigo}
                    value={fam.codigo}
                    className="pl-6 text-sm text-muted-foreground"
                  >
                    {fam.nombre}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>

        {ultimaActualizacion && (
          <p className="text-xs text-muted-foreground sm:ml-auto">
            Actualizado{" "}
            {formatDistanceToNow(ultimaActualizacion, { addSuffix: true, locale: es })}
          </p>
        )}
      </div>

      {/* Tabla */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-36">Código</TableHead>
              <TableHead>Nombre</TableHead>
              <TableHead>Organismo</TableHead>
              <TableHead className="w-28">Estado</TableHead>
              <TableHead className="w-36 text-right">Monto est.</TableHead>
              <TableHead className="w-28">Cierre</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <SkeletonRows />
            ) : !data?.items.length ? (
              <TableRow>
                <TableCell colSpan={6} className="py-10 text-center text-muted-foreground">
                  No se encontraron licitaciones
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((item) => (
                <TableRow
                  key={item.codigo}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => router.push(`/licitaciones/${encodeURIComponent(item.codigo)}`)}
                >
                  <TableCell className="font-mono text-xs">{item.codigo}</TableCell>
                  <TableCell>
                    <span className="line-clamp-2 max-w-xs text-sm">{item.nombre}</span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {item.organismo_nombre ?? "—"}
                  </TableCell>
                  <TableCell>
                    <EstadoBadge estado={item.estado} />
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {formatMontoCLP(item.monto_estimado)}
                  </TableCell>
                  <TableCell className="text-sm">
                    {(() => {
                      const u = urgenciaCierre(item.fecha_cierre, item.estado)
                      return (
                        <span
                          className={
                            u === "urgente"
                              ? "font-semibold text-amber-700"
                              : u === "pronto"
                              ? "text-amber-600"
                              : ""
                          }
                        >
                          {formatFecha(item.fecha_cierre)}
                          {u === "urgente" && (
                            <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-500 align-middle" />
                          )}
                        </span>
                      )
                    })()}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Paginación */}
      {(hasNextPage || hasPrevPage) && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">Página {page}</p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={!hasPrevPage}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasNextPage}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
