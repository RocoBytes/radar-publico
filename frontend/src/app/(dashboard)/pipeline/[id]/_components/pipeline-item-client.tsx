"use client"

import { useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { ArrowLeft, ExternalLink, Trash2 } from "lucide-react"
import { toast } from "sonner"
import {
  getPipelineItem,
  updatePipelineItem,
  createPipelineNota,
  deletePipelineNota,
} from "@/lib/api"
import type { PipelineEstado } from "@/types/pipeline"
import { features } from "@/lib/features"
import { ChecklistSection } from "@/components/feature/pipeline/checklist-section"
import { ScoreBadge } from "@/components/feature/pipeline/score-badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Separator } from "@/components/ui/separator"

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

function formatFechaHora(fecha: string): string {
  try {
    return format(new Date(fecha), "dd/MM/yyyy HH:mm", { locale: es })
  } catch {
    return fecha
  }
}

interface PipelineItemClientProps {
  id: string
}

export function PipelineItemClient({ id }: PipelineItemClientProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [nuevaNota, setNuevaNota] = useState("")
  const [razonDescarte, setRazonDescarte] = useState<string>("")
  const [razonDescarteDirty, setRazonDescarteDirty] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey: ["pipeline-item", id],
    queryFn: () => getPipelineItem(id),
    // Inicializar razonDescarte cuando llega el dato
  })

  // Sincronizar razonDescarte desde el servidor (solo la primera vez)
  const razonDescarteFinal =
    razonDescarteDirty ? razonDescarte : (data?.razon_descarte ?? "")

  const invalidarQueries = () => {
    void queryClient.invalidateQueries({ queryKey: ["pipeline-item", id] })
    void queryClient.invalidateQueries({ queryKey: ["pipeline"] })
  }

  const actualizarEstadoMutation = useMutation({
    mutationFn: (estado: PipelineEstado) => updatePipelineItem(id, { estado }),
    onSuccess: () => {
      toast.success("Estado actualizado")
      invalidarQueries()
    },
    onError: (err: Error) => {
      toast.error(`Error al actualizar: ${err.message}`)
    },
  })

  const actualizarRazonMutation = useMutation({
    mutationFn: (razon_descarte: string) =>
      updatePipelineItem(id, { razon_descarte }),
    onSuccess: () => {
      toast.success("Razón de descarte guardada")
      invalidarQueries()
    },
    onError: (err: Error) => {
      toast.error(`Error al guardar: ${err.message}`)
    },
  })

  const agregarNotaMutation = useMutation({
    mutationFn: () => createPipelineNota(id, nuevaNota.trim()),
    onSuccess: () => {
      toast.success("Nota agregada")
      setNuevaNota("")
      invalidarQueries()
    },
    onError: (err: Error) => {
      toast.error(`Error al agregar nota: ${err.message}`)
    },
  })

  const eliminarNotaMutation = useMutation({
    mutationFn: (notaId: string) => deletePipelineNota(id, notaId),
    onSuccess: () => {
      toast.success("Nota eliminada")
      invalidarQueries()
    },
    onError: (err: Error) => {
      toast.error(`Error al eliminar: ${err.message}`)
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-6 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-10 w-44" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <p className="text-muted-foreground">Item no encontrado</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Botón volver */}
      <Button variant="ghost" size="sm" onClick={() => router.back()} className="-ml-2">
        <ArrowLeft className="mr-2 h-4 w-4" />
        Volver al Pipeline
      </Button>

      {/* Header */}
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${ESTADO_BADGE_CLASE[data.estado]}`}
          >
            {data.estado.charAt(0).toUpperCase() + data.estado.slice(1)}
          </span>
          <ScoreBadge score={data.score} justificacion={data.score_justificacion} />
        </div>
        <h1 className="text-xl font-semibold leading-snug">{data.licitacion.nombre}</h1>
        <p className="text-sm text-muted-foreground">
          {data.licitacion.organismo_nombre ?? "Organismo no especificado"}
        </p>
        <Link
          href={`/licitaciones/${encodeURIComponent(data.licitacion.codigo)}`}
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          Ver licitación
          <ExternalLink className="h-3.5 w-3.5" />
        </Link>
      </div>

      <Separator />

      {/* Cambiar estado */}
      <div className="space-y-2">
        <label className="text-sm font-medium">Estado del seguimiento</label>
        <Select
          value={data.estado}
          onValueChange={(val: string) =>
            actualizarEstadoMutation.mutate(val as PipelineEstado)
          }
          disabled={actualizarEstadoMutation.isPending}
        >
          <SelectTrigger className="w-full sm:w-56">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {ESTADOS_PIPELINE.map((e) => (
              <SelectItem key={e.value} value={e.value}>
                {e.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Razón de descarte — solo si estado es "descartada" */}
      {data.estado === "descartada" && (
        <div className="space-y-2">
          <label className="text-sm font-medium">Razón de descarte</label>
          <Textarea
            placeholder="¿Por qué se descartó esta oportunidad?"
            value={razonDescarteFinal}
            onChange={(e) => {
              setRazonDescarte(e.target.value)
              setRazonDescarteDirty(true)
            }}
            onBlur={() => {
              if (razonDescarteDirty) {
                actualizarRazonMutation.mutate(razonDescarteFinal)
              }
            }}
            rows={3}
          />
        </div>
      )}

      <Separator />

      {/* Notas */}
      <div className="space-y-3">
        <h2 className="text-sm font-medium">Notas</h2>

        {/* Lista de notas existentes */}
        {data.notas.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sin notas aún</p>
        ) : (
          <ul className="space-y-2">
            {data.notas.map((nota) => (
              <li
                key={nota.id}
                className="flex items-start gap-3 rounded-md border px-4 py-3"
              >
                <div className="flex-1 min-w-0 space-y-1">
                  <p className="text-xs text-muted-foreground">
                    {formatFechaHora(nota.created_at)}
                  </p>
                  <p className="text-sm whitespace-pre-wrap">{nota.contenido}</p>
                </div>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>¿Eliminar nota?</AlertDialogTitle>
                      <AlertDialogDescription>
                        Esta acción no se puede deshacer.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancelar</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => eliminarNotaMutation.mutate(nota.id)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Eliminar
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </li>
            ))}
          </ul>
        )}

        {/* Agregar nueva nota */}
        <div className="space-y-2">
          <Textarea
            placeholder="Agregar una nota..."
            value={nuevaNota}
            onChange={(e) => setNuevaNota(e.target.value)}
            rows={3}
          />
          <Button
            size="sm"
            onClick={() => agregarNotaMutation.mutate()}
            disabled={!nuevaNota.trim() || agregarNotaMutation.isPending}
          >
            {agregarNotaMutation.isPending ? "Guardando..." : "Agregar nota"}
          </Button>
        </div>
      </div>

      {/* Checklist documental — gateado por feature flag */}
      {features.pipelineChecklist && (
        <>
          <Separator />
          <ChecklistSection pipelineItemId={id} />
        </>
      )}
    </div>
  )
}
