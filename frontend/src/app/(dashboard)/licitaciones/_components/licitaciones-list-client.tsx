"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Search } from "lucide-react"
import { getLicitaciones } from "@/lib/api"
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
  SelectItem,
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

  // Leer estado inicial desde URL
  const [q, setQ] = useState(searchParams.get("q") ?? "")
  const [estado, setEstado] = useState<LicitacionEstado | "todos">(
    (searchParams.get("estado") as LicitacionEstado) ?? "todos"
  )
  const [page, setPage] = useState(Number(searchParams.get("page") ?? "1"))
  const [debouncedQ, setDebouncedQ] = useState(q)

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
    (nextQ: string, nextEstado: string, nextPage: number) => {
      const params = new URLSearchParams()
      if (nextQ) params.set("q", nextQ)
      if (nextEstado && nextEstado !== "todos") params.set("estado", nextEstado)
      if (nextPage > 1) params.set("page", String(nextPage))
      const query = params.toString()
      router.replace(`/licitaciones${query ? `?${query}` : ""}`, { scroll: false })
    },
    [router]
  )

  useEffect(() => {
    syncUrl(debouncedQ, estado, page)
  }, [debouncedQ, estado, page, syncUrl])

  const filtros: LicitacionFiltros = {
    ...(debouncedQ ? { q: debouncedQ } : {}),
    ...(estado !== "todos" ? { estado } : {}),
    page,
    page_size: 25,
  }

  const { data, isLoading } = useQuery({
    queryKey: ["licitaciones", filtros],
    queryFn: () => getLicitaciones(filtros),
  })

  const totalPages = data?.total_pages ?? 1

  return (
    <div className="space-y-4">
      {/* Filtros */}
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
          onValueChange={(val) => {
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
                    {formatFecha(item.fecha_cierre)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Paginación */}
      {data && totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Página {page} de {totalPages} ({data.total} resultados)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
            >
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
            >
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
