"use client"

import { useQuery } from "@tanstack/react-query"
import { format, isWithinInterval, startOfDay, addDays } from "date-fns"
import { es } from "date-fns/locale"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import { getPipeline } from "@/lib/api"
import type { PipelineListItem } from "@/types/pipeline"

const ESTADO_LABEL: Record<string, string> = {
  nueva: "Nueva",
  evaluando: "Evaluando",
  interesada: "Interesada",
  postulando: "Postulando",
  postulada: "Postulada",
  ganada: "Ganada",
  perdida: "Perdida",
  descartada: "Descartada",
}

function estadoBadgeClass(estado: string): string {
  switch (estado) {
    case "ganada":
      return "bg-green-100 text-green-800 border-transparent"
    case "perdida":
    case "descartada":
      return "bg-red-100 text-red-800 border-transparent"
    case "postulando":
    case "postulada":
      return "bg-blue-100 text-blue-800 border-transparent"
    case "interesada":
    case "evaluando":
      return "bg-yellow-100 text-yellow-800 border-transparent"
    default:
      return "bg-muted text-muted-foreground border-transparent"
  }
}

function CierreRow({ item }: { item: PipelineListItem }) {
  const fecha = new Date(item.licitacion.fecha_cierre!)

  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex w-10 flex-col items-center rounded bg-muted px-1 py-0.5 text-center">
        <span className="text-xs font-bold leading-tight">
          {format(fecha, "d", { locale: es })}
        </span>
        <span className="text-xs uppercase leading-tight text-muted-foreground">
          {format(fecha, "MMM", { locale: es })}
        </span>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.licitacion.nombre}</p>
      </div>
      <Badge className={estadoBadgeClass(item.estado)}>
        {ESTADO_LABEL[item.estado] ?? item.estado}
      </Badge>
    </div>
  )
}

export function CierresProximos() {
  const { data, isLoading } = useQuery({
    queryKey: ["pipeline", { page_size: 20 }],
    queryFn: () => getPipeline({ page_size: 20 }),
  })

  const hoy = startOfDay(new Date())
  const en7Dias = addDays(hoy, 7)

  const proximos = (data?.items ?? [])
    .filter((item) => {
      if (!item.licitacion.fecha_cierre) return false
      const fecha = new Date(item.licitacion.fecha_cierre)
      return isWithinInterval(fecha, { start: hoy, end: en7Dias })
    })
    .sort((a, b) => {
      const fa = new Date(a.licitacion.fecha_cierre!).getTime()
      const fb = new Date(b.licitacion.fecha_cierre!).getTime()
      return fa - fb
    })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cierres próximos</CardTitle>
        <CardDescription>
          Licitaciones en tu pipeline que cierran esta semana
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-10 w-full rounded-md" />
            ))}
          </div>
        ) : proximos.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No hay cierres en los próximos 7 días.
          </p>
        ) : (
          <ScrollArea className="h-48">
            <div className="divide-y">
              {proximos.map((item) => (
                <CierreRow key={item.id} item={item} />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  )
}
