"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Edit2, Plus, Trash2 } from "lucide-react"
import { toast } from "sonner"
import { getRadares, updateRadar, deleteRadar } from "@/lib/api"
import type { Radar } from "@/types/radar"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import { Skeleton } from "@/components/ui/skeleton"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
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
import { RadarDialog } from "./radar-dialog"

function formatUltimaEjecucion(fecha: string | null): string {
  if (!fecha) return "Nunca"
  try {
    return format(new Date(fecha), "dd/MM/yyyy HH:mm", { locale: es })
  } catch {
    return "Nunca"
  }
}

function RadarCardSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex gap-2">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-5 w-20" />
        </div>
        <div className="flex items-center justify-between">
          <Skeleton className="h-4 w-36" />
          <div className="flex gap-2">
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-16" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

interface RadarCardProps {
  radar: Radar
  onEditar: (radar: Radar) => void
}

function RadarCard({ radar, onEditar }: RadarCardProps) {
  const queryClient = useQueryClient()

  const toggleActivoMutation = useMutation({
    mutationFn: () => updateRadar(radar.id, { activo: !radar.activo }),
    onSuccess: () => {
      toast.success(radar.activo ? "Radar desactivado" : "Radar activado")
      void queryClient.invalidateQueries({ queryKey: ["radares"] })
    },
    onError: (err: Error) => {
      toast.error(`Error: ${err.message}`)
    },
  })

  const eliminarMutation = useMutation({
    mutationFn: () => deleteRadar(radar.id),
    onSuccess: () => {
      toast.success("Radar eliminado")
      void queryClient.invalidateQueries({ queryKey: ["radares"] })
    },
    onError: (err: Error) => {
      toast.error(`Error al eliminar: ${err.message}`)
    },
  })

  // Construir badges de filtros activos
  const filtrosBadges: { label: string; value: string }[] = []
  if (radar.filtros.q) filtrosBadges.push({ label: "Búsqueda", value: radar.filtros.q })
  if (radar.filtros.estado) filtrosBadges.push({ label: "Estado", value: radar.filtros.estado })
  if (radar.filtros.tipo) filtrosBadges.push({ label: "Tipo", value: radar.filtros.tipo })
  if (radar.filtros.region) filtrosBadges.push({ label: "Región", value: radar.filtros.region })

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="font-medium truncate">{radar.nombre}</h3>
            {radar.descripcion && (
              <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">
                {radar.descripcion}
              </p>
            )}
          </div>
          <Switch
            checked={radar.activo}
            onCheckedChange={() => toggleActivoMutation.mutate()}
            disabled={toggleActivoMutation.isPending}
            aria-label={radar.activo ? "Desactivar radar" : "Activar radar"}
          />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Filtros activos como badges */}
        {filtrosBadges.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {filtrosBadges.map((f) => (
              <Badge key={f.label} variant="secondary" className="text-xs">
                {f.label}: {f.value}
              </Badge>
            ))}
          </div>
        )}

        {/* Meta info */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
          <div className="flex items-center gap-3">
            <span>
              Notif: <span className="text-foreground capitalize">{radar.notif_canal.replace("_", " ")}</span>
            </span>
            <span>
              Score mín: <span className="text-foreground">{radar.notif_score_minimo}</span>
            </span>
          </div>
          <span className="text-xs">
            Última ejecución: {formatUltimaEjecucion(radar.ultima_ejecucion_at)}
          </span>
        </div>

        {/* Acciones */}
        <div className="flex items-center gap-2 pt-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onEditar(radar)}
          >
            <Edit2 className="mr-1.5 h-3.5 w-3.5" />
            Editar
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="text-destructive hover:text-destructive"
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                Eliminar
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>¿Eliminar radar?</AlertDialogTitle>
                <AlertDialogDescription>
                  Se eliminará el radar <strong>{radar.nombre}</strong>. Esta acción no se puede
                  deshacer.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancelar</AlertDialogCancel>
                <AlertDialogAction
                  onClick={() => eliminarMutation.mutate()}
                  className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                >
                  Eliminar
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardContent>
    </Card>
  )
}

export function RadaresClient() {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [radarEditando, setRadarEditando] = useState<Radar | undefined>(undefined)

  const { data, isLoading } = useQuery({
    queryKey: ["radares"],
    queryFn: getRadares,
  })

  const abrirCrear = () => {
    setRadarEditando(undefined)
    setDialogOpen(true)
  }

  const abrirEditar = (radar: Radar) => {
    setRadarEditando(radar)
    setDialogOpen(true)
  }

  return (
    <div className="space-y-4">
      {/* Botón crear */}
      <div className="flex justify-end">
        <Button onClick={abrirCrear}>
          <Plus className="mr-2 h-4 w-4" />
          Nuevo Radar
        </Button>
      </div>

      {/* Cards */}
      <div className="grid gap-4 sm:grid-cols-2">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <RadarCardSkeleton key={i} />)
        ) : !data?.items.length ? (
          <div className="col-span-full rounded-md border py-12 text-center text-muted-foreground">
            No tenés radares configurados todavía.{" "}
            <button
              onClick={abrirCrear}
              className="cursor-pointer text-primary underline underline-offset-2"
            >
              Crear el primero
            </button>
          </div>
        ) : (
          data.items.map((radar) => (
            <RadarCard key={radar.id} radar={radar} onEditar={abrirEditar} />
          ))
        )}
      </div>

      {/* Dialog crear/editar */}
      <RadarDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        radar={radarEditando}
      />
    </div>
  )
}
