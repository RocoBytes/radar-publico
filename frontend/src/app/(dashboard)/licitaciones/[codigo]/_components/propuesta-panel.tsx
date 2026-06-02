"use client"

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Download,
  FileCheck,
  FileText,
  Loader2,
  Wand2,
} from "lucide-react"
import { toast } from "sonner"
import { getBorradorPropuesta, triggerBorradorPropuesta } from "@/lib/api"
import type { BorradorPropuesta, SeccionPropuesta } from "@/types/licitacion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface PropuestaPanelProps {
  codigo: string
}

function SeccionCard({ seccion, index }: { seccion: SeccionPropuesta; index: number }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold">
          <Badge variant="outline" className="text-xs font-mono px-1.5">
            {String(index + 1).padStart(2, "0")}
          </Badge>
          {seccion.titulo}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{seccion.contenido}</p>
      </CardContent>
    </Card>
  )
}

function BorradorContent({ borrador }: { borrador: BorradorPropuesta }) {
  return (
    <div className="space-y-6">
      {/* Título del borrador */}
      {borrador.titulo && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <FileText className="h-4 w-4 text-primary" />
              Propuesta técnica
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-base font-semibold">{borrador.titulo}</p>
          </CardContent>
        </Card>
      )}

      {/* Secciones */}
      {(borrador.secciones?.length ?? 0) > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold text-primary">Contenido del borrador</h3>
          {borrador.secciones!.map((s, i) => (
            <SeccionCard key={i} seccion={s} index={i} />
          ))}
        </section>
      )}

      {/* Documentos pendientes */}
      {(borrador.documentos_pendientes?.length ?? 0) > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-primary mb-3">Documentos a preparar</h3>
          <ul className="rounded-md border px-4 divide-y divide-border">
            {borrador.documentos_pendientes!.map((doc, i) => (
              <li key={i} className="flex items-center gap-2 py-2.5">
                <FileCheck className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="text-sm">{doc}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Notas de revisión */}
      {(borrador.notas_revision?.length ?? 0) > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-primary mb-3">Notas de revisión</h3>
          <ul className="space-y-2">
            {borrador.notas_revision!.map((nota, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-yellow-500" />
                <span>{nota}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Metadata discreta */}
      {borrador.modelo_usado && (
        <p className="text-xs text-muted-foreground">
          Generado con {borrador.modelo_usado}
        </p>
      )}
    </div>
  )
}

export function PropuestaPanel({ codigo }: PropuestaPanelProps) {
  const queryClient = useQueryClient()
  const [exportando, setExportando] = useState(false)

  const handleExportDocx = async () => {
    setExportando(true)
    try {
      const res = await fetch(
        `/api/licitaciones/${encodeURIComponent(codigo)}/propuesta/export`,
        { credentials: "include" }
      )
      if (!res.ok) throw new Error("Error al exportar el borrador")
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `propuesta-${codigo}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch {
      toast.error("No se pudo exportar el DOCX")
    } finally {
      setExportando(false)
    }
  }

  const { data, isLoading, error } = useQuery({
    queryKey: ["borrador-propuesta", codigo],
    queryFn: () => getBorradorPropuesta(codigo),
    retry: false,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === "pendiente" || s === "procesando" ? 4000 : false
    },
  })

  const triggerMutation = useMutation({
    mutationFn: () => triggerBorradorPropuesta(codigo),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["borrador-propuesta", codigo] })
    },
    onError: (err: Error) => {
      toast.error(err.message)
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  // Sin borrador todavía (404)
  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <Wand2 className="h-10 w-10 text-muted-foreground/40" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Sin borrador disponible</p>
          <p className="text-xs text-muted-foreground max-w-sm">
            El borrador genera una propuesta técnica personalizada con el perfil de tu empresa,
            los criterios de evaluación y los requisitos de las bases.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
        >
          {triggerMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Wand2 className="mr-2 h-4 w-4" />
          )}
          Generar borrador
        </Button>
      </div>
    )
  }

  // Procesando / pendiente
  if (data.status === "pendiente" || data.status === "procesando") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Generando borrador de propuesta...</p>
          <p className="text-xs text-muted-foreground">
            El borrador tarda entre 30 y 90 segundos dependiendo de la complejidad.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          Actualizando automáticamente...
        </div>
      </div>
    )
  }

  // Error en la generación
  if (data.status === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <div className="space-y-1">
          <p className="text-sm font-medium">No se pudo generar el borrador</p>
          {data.error_mensaje && (
            <p className="text-xs text-muted-foreground max-w-sm">{data.error_mensaje}</p>
          )}
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
        >
          {triggerMutation.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <AlertCircle className="mr-2 h-4 w-4" />
          )}
          Reintentar
        </Button>
      </div>
    )
  }

  // Listo
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground pb-2">
        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
        Borrador generado
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="h-7 text-xs"
            onClick={handleExportDocx}
            disabled={exportando}
          >
            {exportando ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="mr-1.5 h-3.5 w-3.5" />
            )}
            Exportar DOCX
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 text-xs"
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
          >
            Volver a generar
          </Button>
        </div>
      </div>
      <BorradorContent borrador={data} />
    </div>
  )
}
