"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { ArrowLeft, Bot, BrainCircuit, ExternalLink, Plus, Sparkles, Wand2 } from "lucide-react"
import { toast } from "sonner"
import { getLicitacion, createPipelineItem } from "@/lib/api"
import { AnalisisPanel } from "./analisis-panel"
import { ChatPanel } from "./chat-panel"
import { InteligenciaPanel } from "./inteligencia-panel"
import { PropuestaPanel } from "./propuesta-panel"
import type { LicitacionEstado } from "@/types/licitacion"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

const BADGE_VARIANTE: Record<LicitacionEstado, string> = {
  publicada: "bg-green-100 text-green-800 border-green-200",
  cerrada: "bg-yellow-100 text-yellow-800 border-yellow-200",
  adjudicada: "bg-blue-100 text-blue-800 border-blue-200",
  desierta: "bg-slate-100 text-slate-600 border-slate-200",
  revocada: "bg-slate-100 text-slate-600 border-slate-200",
  suspendida: "bg-slate-100 text-slate-600 border-slate-200",
}

function formatMontoCLP(monto: number | null): string {
  if (monto === null) return "—"
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(monto)
}

function formatFecha(fecha: string | null | undefined): string {
  if (!fecha) return "—"
  try {
    return format(new Date(fecha), "dd/MM/yyyy HH:mm", { locale: es })
  } catch {
    return "—"
  }
}

function DetalleRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <dt className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
        {label}
      </dt>
      <dd className="text-sm">{value ?? "—"}</dd>
    </div>
  )
}

function HeaderSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-8 w-3/4" />
      <Skeleton className="h-5 w-1/2" />
      <div className="flex gap-3">
        <Skeleton className="h-6 w-20" />
        <Skeleton className="h-6 w-32" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-9 w-36" />
        <Skeleton className="h-9 w-40" />
      </div>
    </div>
  )
}

interface LicitacionDetalleClientProps {
  codigo: string
}

export function LicitacionDetalleClient({ codigo }: LicitacionDetalleClientProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const [agregandoPipeline, setAgregandoPipeline] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ["licitacion", codigo],
    queryFn: () => getLicitacion(codigo),
  })

  const agregarPipelineMutation = useMutation({
    mutationFn: () => createPipelineItem({ licitacion_codigo: codigo }),
    onMutate: () => setAgregandoPipeline(true),
    onSettled: () => setAgregandoPipeline(false),
    onSuccess: () => {
      toast.success("Licitación agregada al pipeline")
      void queryClient.invalidateQueries({ queryKey: ["pipeline"] })
    },
    onError: (err: Error) => {
      toast.error(`Error al agregar al pipeline: ${err.message}`)
    },
  })

  const urlMercadoPublico = `https://www.mercadopublico.cl/Procurement/Modules/RFB/DetailsAcquisition.aspx?idlicitacion=${encodeURIComponent(codigo)}`

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <p className="text-destructive">Error al cargar la licitación</p>
        <Button variant="outline" onClick={() => router.back()} className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Volver
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Botón volver */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.back()}
        className="-ml-2"
      >
        <ArrowLeft className="mr-2 h-4 w-4" />
        Volver a oportunidades
      </Button>

      {/* Header */}
      {isLoading ? (
        <HeaderSkeleton />
      ) : data ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-start gap-2">
            <span
              className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${BADGE_VARIANTE[data.estado]}`}
            >
              {data.estado.charAt(0).toUpperCase() + data.estado.slice(1)}
            </span>
            <span className="font-mono text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">
              {data.codigo}
            </span>
          </div>
          <h1 className="text-2xl font-semibold tracking-tight leading-snug">
            {data.nombre}
          </h1>
          <p className="text-muted-foreground">
            {data.organismo_nombre ?? "Organismo no especificado"}
          </p>
          <p className="text-xl font-medium">
            {formatMontoCLP(data.monto_estimado)}
            {data.moneda && data.moneda !== "CLP" && (
              <span className="ml-1 text-sm text-muted-foreground">{data.moneda}</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" asChild>
              <a href={urlMercadoPublico} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-4 w-4" />
                Ver en Mercado Público
              </a>
            </Button>
            <Button
              size="sm"
              onClick={() => agregarPipelineMutation.mutate()}
              disabled={agregandoPipeline}
            >
              <Plus className="mr-2 h-4 w-4" />
              {agregandoPipeline ? "Agregando..." : "Agregar al Pipeline"}
            </Button>
          </div>
        </div>
      ) : null}


      {/* Tabs de contenido */}
      {isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-full max-w-sm" />
          <Skeleton className="h-48 w-full" />
        </div>
      ) : data ? (
        <Tabs defaultValue="resumen">
          <TabsList>
            <TabsTrigger value="resumen">Resumen</TabsTrigger>
            <TabsTrigger value="calendario">
              Calendario
              {(data.fechas?.length ?? 0) > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-xs px-1.5">
                  {data.fechas.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="bases">
              Bases
              {(data.documentos?.length ?? 0) > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-xs px-1.5">
                  {data.documentos.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="items">
              Items
              {(data.items?.length ?? 0) > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-xs px-1.5">
                  {data.items.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="analisis">
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              Análisis IA
            </TabsTrigger>
            <TabsTrigger value="propuesta">
              <Wand2 className="mr-1.5 h-3.5 w-3.5" />
              Propuesta IA
            </TabsTrigger>
            <TabsTrigger value="inteligencia">
              <BrainCircuit className="mr-1.5 h-3.5 w-3.5" />
              Inteligencia
            </TabsTrigger>
            <TabsTrigger value="chat">
              <Bot className="mr-1.5 h-3.5 w-3.5" />
              Asistente IA
            </TabsTrigger>
          </TabsList>

          {/* Tab: Resumen */}
          <TabsContent value="resumen" className="mt-4 space-y-6">
            {/* 1. Características de la licitación */}
            <section>
              <h2 className="text-sm font-semibold text-primary mb-3">
                1. Características de la licitación
              </h2>
              <div className="rounded-md border p-4">
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <DetalleRow label="Descripción" value={data.descripcion} />
                  <DetalleRow label="Tipo de licitación" value={data.tipo} />
                  <DetalleRow label="Tipo de convocatoria" value={data.modalidad} />
                  <DetalleRow label="Moneda" value={data.moneda} />
                  <DetalleRow
                    label="Renovable"
                    value={data.es_renovable ? "Sí" : "No"}
                  />
                  <DetalleRow
                    label="Duración estimada"
                    value={
                      data.duracion_estimada_meses
                        ? `${data.duracion_estimada_meses} meses`
                        : null
                    }
                  />
                  <DetalleRow
                    label="Fecha publicación"
                    value={formatFecha(data.fecha_publicacion)}
                  />
                  <DetalleRow
                    label="Fecha cierre"
                    value={formatFecha(data.fecha_cierre)}
                  />
                </dl>
              </div>
            </section>

            {/* 2. Organismo demandante */}
            <section>
              <h2 className="text-sm font-semibold text-primary mb-3">
                2. Organismo demandante
              </h2>
              <div className="rounded-md border p-4">
                <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <DetalleRow label="Razón social" value={data.organismo_nombre} />
                  <DetalleRow label="Unidad de compra" value={data.unidad_compra} />
                  <DetalleRow label="R.U.T." value={data.organismo_rut ?? data.rut_unidad} />
                  <DetalleRow label="Región" value={data.organismo_region} />
                  <DetalleRow label="Comuna" value={data.organismo_comuna} />
                  <DetalleRow label="Dirección" value={data.organismo_direccion} />
                  {data.organismo_ministerio && (
                    <DetalleRow label="Ministerio" value={data.organismo_ministerio} />
                  )}
                </dl>
              </div>
            </section>

            {/* 3. Contacto */}
            {(data.contacto_nombre ?? data.contacto_email ?? data.contacto_telefono) && (
              <section>
                <h2 className="text-sm font-semibold text-primary mb-3">
                  3. Contacto
                </h2>
                <div className="rounded-md border p-4">
                  <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <DetalleRow label="Nombre" value={data.contacto_nombre} />
                    <DetalleRow label="Email" value={data.contacto_email} />
                    <DetalleRow label="Teléfono" value={data.contacto_telefono} />
                  </dl>
                </div>
              </section>
            )}
          </TabsContent>

          {/* Tab: Calendario */}
          <TabsContent value="calendario" className="mt-4">
            {(data.fechas ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">Sin fechas registradas</p>
            ) : (
              <ol className="relative border-l border-border ml-3 space-y-4">
                {data.fechas.map((f, idx) => (
                  <li key={idx} className="ml-4">
                    <div className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border border-background bg-primary" />
                    <p className="text-xs text-muted-foreground">{formatFecha(f.fecha)}</p>
                    <p className="text-sm font-medium">{f.tipo}</p>
                  </li>
                ))}
              </ol>
            )}
          </TabsContent>

          {/* Tab: Bases */}
          <TabsContent value="bases" className="mt-4">
            {(data.documentos ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">Sin bases disponibles</p>
            ) : (
              <ul className="space-y-2">
                {data.documentos.map((doc) => (
                  <li key={doc.id} className="flex items-center justify-between rounded-md border px-4 py-3">
                    <span className="text-sm">{doc.nombre}</span>
                    {(doc.url_r2 ?? doc.url_portal) ? (
                      <Button variant="ghost" size="sm" asChild>
                        <a
                          href={(doc.url_r2 ?? doc.url_portal) ?? "#"}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <ExternalLink className="mr-1 h-4 w-4" />
                          Descargar
                        </a>
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground">No disponible</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </TabsContent>

          {/* Tab: Items */}
          <TabsContent value="items" className="mt-4">
            {(data.items ?? []).length === 0 ? (
              <p className="text-sm text-muted-foreground py-4">Sin items</p>
            ) : (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-12">#</TableHead>
                      <TableHead>Descripción</TableHead>
                      <TableHead className="w-24 text-right">Cantidad</TableHead>
                      <TableHead className="w-24">Unidad</TableHead>
                      <TableHead className="w-32 text-right">UNSPSC</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.items.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="text-muted-foreground">{item.numero_item}</TableCell>
                        <TableCell className="text-sm">{item.descripcion ?? "—"}</TableCell>
                        <TableCell className="text-right text-sm">{item.cantidad ?? "—"}</TableCell>
                        <TableCell className="text-sm">{item.unidad ?? "—"}</TableCell>
                        <TableCell className="text-right font-mono text-xs text-muted-foreground">
                          {item.unspsc_codigo ?? "—"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>

          {/* Tab: Análisis IA */}
          <TabsContent value="analisis" className="mt-4">
            <AnalisisPanel codigo={codigo} />
          </TabsContent>

          {/* Tab: Propuesta IA */}
          <TabsContent value="propuesta" className="mt-4">
            <PropuestaPanel codigo={codigo} />
          </TabsContent>

          {/* Tab: Inteligencia */}
          <TabsContent value="inteligencia" className="mt-4">
            <InteligenciaPanel codigo={codigo} />
          </TabsContent>

          {/* Tab: Asistente IA */}
          <TabsContent value="chat" className="mt-4">
            <ChatPanel codigo={codigo} />
          </TabsContent>
        </Tabs>
      ) : null}
    </div>
  )
}
