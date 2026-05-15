"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"
import { differenceInCalendarDays, format, startOfDay } from "date-fns"
import { es } from "date-fns/locale"
import { MessageSquare } from "lucide-react"
import { getPipeline } from "@/lib/api"
import type { PipelineEstado } from "@/types/pipeline"
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
import { Card, CardContent } from "@/components/ui/card"

const ESTADOS_PIPELINE: { value: PipelineEstado; label: string }[] = [
  { value: "nueva", label: "Nueva" },
  { value: "evaluando", label: "Evaluando" },
  { value: "interesada", label: "Interesada" },
  { value: "postulando", label: "Postulando" },
  { value: "postulada", label: "Postulada" },
  { value: "ganada", label: "Ganada" },
  { value: "perdida", label: "Perdida" },
  { value: "descartada", label: "Descartada" },
]

const ESTADO_BADGE_CLASE: Record<PipelineEstado, string> = {
  nueva: "bg-slate-100 text-slate-700 border-slate-200",
  evaluando: "bg-yellow-100 text-yellow-800 border-yellow-200",
  interesada: "bg-blue-100 text-blue-800 border-blue-200",
  postulando: "bg-purple-100 text-purple-800 border-purple-200",
  postulada: "bg-purple-100 text-purple-800 border-purple-200",
  ganada: "bg-green-100 text-green-800 border-green-200",
  perdida: "bg-red-100 text-red-800 border-red-200",
  descartada: "bg-red-100 text-red-800 border-red-200",
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <span className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 text-sm font-semibold border border-slate-200">
        —
      </span>
    )
  }
  const claseColor =
    score >= 70
      ? "bg-green-100 text-green-800 border-green-300"
      : score >= 40
        ? "bg-yellow-100 text-yellow-800 border-yellow-300"
        : "bg-slate-100 text-slate-600 border-slate-200"

  return (
    <span
      className={`inline-flex h-12 w-12 items-center justify-center rounded-full text-sm font-bold border ${claseColor}`}
    >
      {score}
    </span>
  )
}

function PipelineCardSkeleton() {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-start gap-4">
          <Skeleton className="h-12 w-12 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-3 w-1/2" />
            <div className="flex gap-2">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-5 w-24" />
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

function formatFecha(fecha: string | null | undefined): string {
  if (!fecha) return "—"
  try {
    return format(new Date(fecha), "dd/MM/yyyy", { locale: es })
  } catch {
    return "—"
  }
}

const ESTADOS_ACTIVOS_PIPELINE = new Set(["nueva", "evaluando", "interesada", "postulando", "postulada"])

function urgenciaCierre(fecha: string | null | undefined, estado: PipelineEstado): "urgente" | "pronto" | null {
  if (!fecha || !ESTADOS_ACTIVOS_PIPELINE.has(estado)) return null
  try {
    const dias = differenceInCalendarDays(new Date(fecha), startOfDay(new Date()))
    if (dias <= 1) return "urgente"
    if (dias <= 3) return "pronto"
  } catch {
    return null
  }
  return null
}

export function PipelineListClient() {
  const router = useRouter()
  const [estado, setEstado] = useState<PipelineEstado | "todos">("todos")
  const [scoreMin, setScoreMin] = useState<string>("")
  const [page, setPage] = useState(1)

  const params = {
    ...(estado !== "todos" ? { estado } : {}),
    ...(scoreMin ? { score_min: Number(scoreMin) } : {}),
    page,
    page_size: 25,
  }

  const { data, isLoading } = useQuery({
    queryKey: ["pipeline", params],
    queryFn: () => getPipeline(params),
  })

  const totalPages = data?.total_pages ?? 1

  return (
    <div className="space-y-4">
      {/* Filtros */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <Select
          value={estado}
          onValueChange={(val: string) => {
            setEstado(val as PipelineEstado | "todos")
            setPage(1)
          }}
        >
          <SelectTrigger className="w-full sm:w-44">
            <SelectValue placeholder="Estado" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos los estados</SelectItem>
            {ESTADOS_PIPELINE.map((e) => (
              <SelectItem key={e.value} value={e.value}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          type="number"
          placeholder="Score mínimo (0-100)"
          value={scoreMin}
          min={0}
          max={100}
          onChange={(e) => {
            setScoreMin(e.target.value)
            setPage(1)
          }}
          className="w-full sm:w-52"
        />
      </div>

      {/* Cards */}
      <div className="space-y-3">
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <PipelineCardSkeleton key={i} />)
        ) : !data?.items.length ? (
          <div className="rounded-lg border py-16 text-center">
            <p className="text-sm font-medium text-foreground">Tu pipeline está vacío</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Explorá las oportunidades y agregá licitaciones a tu pipeline.
            </p>
          </div>
        ) : (
          data.items.map((item) => (
            <Card
              key={item.id}
              className="cursor-pointer hover:bg-muted/30 transition-colors"
              onClick={() => router.push(`/pipeline/${item.id}`)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-4">
                  <div className="shrink-0">
                    <ScoreBadge score={item.score} />
                  </div>
                  <div className="flex-1 min-w-0 space-y-1.5">
                    <p className="font-medium leading-snug truncate">
                      {item.licitacion.nombre}
                    </p>
                    <p className="text-sm text-muted-foreground truncate">
                      {item.licitacion.organismo_nombre ?? "Organismo no especificado"}
                    </p>
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${ESTADO_BADGE_CLASE[item.estado]}`}
                      >
                        {item.estado.charAt(0).toUpperCase() + item.estado.slice(1)}
                      </span>
                      {item.licitacion.fecha_cierre && (() => {
                        const u = urgenciaCierre(item.licitacion.fecha_cierre, item.estado)
                        return (
                          <span
                            className={`text-xs ${
                              u === "urgente"
                                ? "font-semibold text-amber-700"
                                : u === "pronto"
                                ? "text-amber-600"
                                : "text-muted-foreground"
                            }`}
                          >
                            Cierre: {formatFecha(item.licitacion.fecha_cierre)}
                            {u === "urgente" && (
                              <span className="ml-1.5 inline-block h-1.5 w-1.5 rounded-full bg-amber-500 align-middle" />
                            )}
                          </span>
                        )
                      })()}
                      {item.notas_count > 0 && (
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <MessageSquare className="h-3 w-3" />
                          {item.notas_count}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        )}
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
