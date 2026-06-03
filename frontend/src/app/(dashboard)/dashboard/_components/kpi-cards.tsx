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
      iconBg: "bg-primary/10",
      iconColor: "text-primary",
    },
    {
      label: "Nuevas hoy",
      icon: Sparkles,
      value: data?.nuevas_hoy ?? 0,
      iconBg: "bg-blue-100",
      iconColor: "text-blue-700",
    },
    {
      label: "Próximas a cerrar",
      icon: Clock,
      value: data?.proximas_a_cerrar ?? 0,
      iconBg: "bg-amber-100",
      iconColor: "text-amber-700",
    },
    {
      label: "En mi pipeline",
      icon: Kanban,
      value: data?.en_pipeline ?? 0,
      iconBg: "bg-slate-100",
      iconColor: "text-slate-600",
    },
  ]

  const sincLabel = data?.ultima_sincronizacion
    ? `Últ. sync: ${format(new Date(data.ultima_sincronizacion), "d MMM HH:mm", { locale: es })}`
    : "Sin datos de sincronización"

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {kpis.map(({ label, icon: Icon, value, iconBg, iconColor }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {label}
              </CardTitle>
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${iconBg}`}
              >
                <Icon className={`h-4 w-4 ${iconColor}`} />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold tracking-tight">
                {value.toLocaleString("es-CL")}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">{sincLabel}</p>
    </div>
  )
}
