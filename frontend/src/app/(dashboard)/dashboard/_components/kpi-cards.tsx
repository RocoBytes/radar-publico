"use client"

import { useQuery } from "@tanstack/react-query"
import { TrendingUp, Sparkles, Clock, Kanban } from "lucide-react"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardResumen } from "@/lib/api"

export function KpiCards() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-resumen"],
    queryFn: getDashboardResumen,
  })

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-lg" />
        ))}
      </div>
    )
  }

  const kpis = [
    {
      label: "Oportunidades activas",
      icon: TrendingUp,
      value: data?.oportunidades_activas ?? 0,
    },
    {
      label: "Nuevas hoy",
      icon: Sparkles,
      value: data?.nuevas_hoy ?? 0,
    },
    {
      label: "Próximas a cerrar",
      icon: Clock,
      value: data?.proximas_a_cerrar ?? 0,
    },
    {
      label: "En mi pipeline",
      icon: Kanban,
      value: data?.en_pipeline ?? 0,
    },
  ]

  const sincLabel = data?.ultima_sincronizacion
    ? `Última sincronización: ${format(new Date(data.ultima_sincronizacion), "d MMM yyyy HH:mm", { locale: es })}`
    : "Sin datos"

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map(({ label, icon: Icon, value }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{label}</CardTitle>
              <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{sincLabel}</p>
    </div>
  )
}
