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
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardSegmentos } from "@/lib/api"

function truncarNombre(nombre: string, max = 20): string {
  return nombre.length > max ? nombre.slice(0, max) + "…" : nombre
}

export function SegmentosChart() {
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
        <CardTitle>Licitaciones por rubro</CardTitle>
        <CardDescription>Segmentos UNSPSC activos</CardDescription>
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
            <BarChart data={segmentos}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="nombre" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar
                dataKey="cantidad"
                fill="hsl(var(--primary))"
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
