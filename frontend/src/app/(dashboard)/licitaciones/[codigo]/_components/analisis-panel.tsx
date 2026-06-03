"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileCheck,
  Loader2,
  Sparkles,
} from "lucide-react"
import { toast } from "sonner"
import { getAnalisisBases, triggerAnalisisBases } from "@/lib/api"
import type {
  AnalisisBases,
  CriterioExtraido,
  DocumentoObligatorio,
  PlazoClave,
  RequisitoTecnico,
} from "@/types/licitacion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

interface AnalisisPanelProps {
  codigo: string
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-primary mb-3">{children}</h3>
  )
}

function RequisitoCard({ req }: { req: RequisitoTecnico }) {
  return (
    <div className="rounded-md border p-3 space-y-1">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium leading-snug">{req.descripcion}</p>
        <Badge
          variant="outline"
          className={
            req.tipo === "obligatorio"
              ? "shrink-0 border-red-200 text-red-700 bg-red-50"
              : "shrink-0 border-yellow-200 text-yellow-700 bg-yellow-50"
          }
        >
          {req.tipo}
        </Badge>
      </div>
      {req.detalle && (
        <p className="text-xs text-muted-foreground leading-relaxed">{req.detalle}</p>
      )}
    </div>
  )
}

function CriterioRow({ criterio }: { criterio: CriterioExtraido }) {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{criterio.nombre}</p>
        {criterio.descripcion && (
          <p className="text-xs text-muted-foreground mt-0.5 truncate">
            {criterio.descripcion}
          </p>
        )}
      </div>
      <span className="ml-4 shrink-0 text-sm font-semibold tabular-nums">
        {criterio.peso_pct}%
      </span>
    </div>
  )
}

function DocumentoRow({ doc }: { doc: DocumentoObligatorio }) {
  return (
    <li className="flex items-start gap-2 py-2 border-b last:border-0">
      <FileCheck className="h-4 w-4 mt-0.5 shrink-0 text-muted-foreground" />
      <div>
        <p className="text-sm font-medium">{doc.nombre}</p>
        {doc.descripcion && (
          <p className="text-xs text-muted-foreground mt-0.5">{doc.descripcion}</p>
        )}
      </div>
    </li>
  )
}

function PlazoRow({ plazo }: { plazo: PlazoClave }) {
  return (
    <li className="ml-4 relative">
      <div className="absolute -left-[1.35rem] mt-1.5 h-3 w-3 rounded-full border border-background bg-primary" />
      <p className="text-xs text-muted-foreground">{plazo.fecha_texto}</p>
      <p className="text-sm font-medium">{plazo.tipo.replace(/_/g, " ")}</p>
      {plazo.descripcion && (
        <p className="text-xs text-muted-foreground mt-0.5">{plazo.descripcion}</p>
      )}
    </li>
  )
}

function AnalisisContent({ analisis }: { analisis: AnalisisBases }) {
  return (
    <div className="space-y-6">
      {/* Resumen ejecutivo */}
      {analisis.resumen_ejecutivo && (
        <Card className="border-primary/20 bg-primary/5">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm font-medium">
              <Sparkles className="h-4 w-4 text-primary" />
              Resumen del análisis
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm leading-relaxed">{analisis.resumen_ejecutivo}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Criterios de evaluación */}
        {(analisis.criterios_extraidos?.length ?? 0) > 0 && (
          <section>
            <SectionTitle>Criterios de evaluación</SectionTitle>
            <div className="rounded-md border px-4 divide-y divide-border">
              {analisis.criterios_extraidos!.map((c, i) => (
                <CriterioRow key={i} criterio={c} />
              ))}
            </div>
          </section>
        )}

        {/* Documentos obligatorios */}
        {(analisis.documentos_obligatorios?.length ?? 0) > 0 && (
          <section>
            <SectionTitle>Documentos requeridos</SectionTitle>
            <ul className="rounded-md border px-4 divide-y divide-border">
              {analisis.documentos_obligatorios!.map((d, i) => (
                <DocumentoRow key={i} doc={d} />
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Requisitos técnicos */}
      {(analisis.requisitos_tecnicos?.length ?? 0) > 0 && (
        <section>
          <SectionTitle>Requisitos técnicos</SectionTitle>
          <div className="grid gap-2 sm:grid-cols-2">
            {analisis.requisitos_tecnicos!.map((r, i) => (
              <RequisitoCard key={i} req={r} />
            ))}
          </div>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Plazos clave */}
        {(analisis.plazos_clave?.length ?? 0) > 0 && (
          <section>
            <SectionTitle>Plazos clave</SectionTitle>
            <ol className="relative border-l border-border ml-3 space-y-4">
              {analisis.plazos_clave!.map((p, i) => (
                <PlazoRow key={i} plazo={p} />
              ))}
            </ol>
          </section>
        )}

        {/* Restricciones */}
        {(analisis.restricciones?.length ?? 0) > 0 && (
          <section>
            <SectionTitle>Restricciones y exclusiones</SectionTitle>
            <ul className="space-y-2">
              {analisis.restricciones!.map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-yellow-500" />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>

      {/* Metadata discreta */}
      {analisis.modelo_usado && (
        <p className="text-xs text-muted-foreground">
          Analizado con {analisis.modelo_usado}
          {analisis.tokens_input
            ? ` · ${(analisis.tokens_input / 1000).toFixed(1)}k tokens`
            : ""}
        </p>
      )}
    </div>
  )
}

export function AnalisisPanel({ codigo }: AnalisisPanelProps) {
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ["analisis-bases", codigo],
    queryFn: () => getAnalisisBases(codigo),
    retry: false,
    refetchInterval: (query) => {
      const s = query.state.data?.status
      return s === "pendiente" || s === "procesando" ? 4000 : false
    },
  })

  const triggerMutation = useMutation({
    mutationFn: () => triggerAnalisisBases(codigo),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["analisis-bases", codigo] })
    },
    onError: (err: Error) => {
      toast.error(err.message)
    },
  })

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-24 w-full" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    )
  }

  // Sin análisis todavía (404)
  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <Sparkles className="h-10 w-10 text-muted-foreground/40" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Sin análisis disponible</p>
          <p className="text-xs text-muted-foreground max-w-sm">
            El análisis de bases extrae requisitos, criterios, documentos y plazos
            directamente del PDF de bases técnicas.
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
            <Sparkles className="mr-2 h-4 w-4" />
          )}
          Solicitar análisis
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
          <p className="text-sm font-medium">Analizando las bases técnicas...</p>
          <p className="text-xs text-muted-foreground">
            El análisis tarda entre 30 y 120 segundos dependiendo del tamaño del documento.
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Clock className="h-3.5 w-3.5" />
          Actualizando automáticamente...
        </div>
      </div>
    )
  }

  // Error en el análisis
  if (data.status === "error") {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
        <div className="space-y-1">
          <p className="text-sm font-medium">El análisis falló</p>
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
          Reintentar análisis
        </Button>
      </div>
    )
  }

  // Listo
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs text-muted-foreground pb-2">
        <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
        Análisis completado
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto h-7 text-xs"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending}
        >
          Volver a analizar
        </Button>
      </div>
      <AnalisisContent analisis={data} />
    </div>
  )
}
