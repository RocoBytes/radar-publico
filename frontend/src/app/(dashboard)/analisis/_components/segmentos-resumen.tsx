"use client"

import { useQuery } from "@tanstack/react-query"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardSegmentos } from "@/lib/api"

function truncarNombre(nombre: string, max = 18): string {
  return nombre.length > max ? nombre.slice(0, max) + "…" : nombre
}

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: Array<{ value: number }>
  label?: string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border bg-white px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-bold text-primary">
        {payload[0]?.value} licitaciones
      </p>
    </div>
  )
}

export function SegmentosResumen() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-segmentos"],
    queryFn: () => getDashboardSegmentos(),
  })

  const segmentos = (data?.segmentos ?? []).slice(0, 8).map((s) => ({
    ...s,
    nombre: truncarNombre(s.nombre),
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Distribución por rubro UNSPSC</CardTitle>
        <CardDescription>Segmentos activos con mayor volumen de licitaciones</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : segmentos.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center">
            <p className="text-sm text-muted-foreground">
              No hay datos de segmentos disponibles
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={segmentos} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 20% 88%)" vertical={false} />
              <XAxis
                dataKey="nombre"
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(220 20% 88%)" }}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={{ fill: "hsl(220 14% 96%)" }}
              />
              <Bar
                dataKey="cantidad"
                fill="hsl(var(--primary))"
                radius={[4, 4, 0, 0]}
                maxBarSize={48}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
