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
import { getDashboardTopOrganismos } from "@/lib/api"

function truncarNombre(nombre: string, max = 25): string {
  return nombre.length > max ? nombre.slice(0, max) + "…" : nombre
}

function formatMonto(monto: number | null): string {
  if (monto === null) return "—"
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(monto)
}

interface TooltipPayloadEntry {
  payload: { nombreCompleto: string; cantidad: number; monto_total: number | null }
}

interface CustomTooltipProps {
  active?: boolean
  payload?: TooltipPayloadEntry[]
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  if (!d) return null
  return (
    <div className="max-w-[220px] rounded-lg border bg-white px-3 py-2 shadow-lg">
      <p className="text-xs font-medium leading-snug text-foreground">{d.nombreCompleto}</p>
      <p className="mt-0.5 text-sm font-bold text-primary">
        {d.cantidad} licitacion{d.cantidad !== 1 ? "es" : ""}
      </p>
      {d.monto_total !== null && (
        <p className="text-xs text-muted-foreground">
          Monto: {formatMonto(d.monto_total)}
        </p>
      )}
    </div>
  )
}

export function TopOrganismosChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-top-organismos", 10, 12],
    queryFn: () => getDashboardTopOrganismos(10, 12),
  })

  const organismos = (data?.organismos ?? []).map((o) => ({
    ...o,
    nombreCompleto: o.nombre,
    nombre: truncarNombre(o.nombre),
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top organismos</CardTitle>
        <CardDescription>
          Los 10 organismos con más licitaciones publicadas (últimos 12 meses)
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : organismos.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center">
            <p className="text-sm text-muted-foreground">
              No hay datos de organismos disponibles
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={organismos} layout="vertical" margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 20% 88%)" horizontal={false} />
              <XAxis
                type="number"
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(220 20% 88%)" }}
              />
              <YAxis
                type="category"
                dataKey="nombre"
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={false}
                width={130}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "hsl(220 14% 96%)" }} />
              <Bar
                dataKey="cantidad"
                fill="hsl(var(--primary))"
                radius={[0, 4, 4, 0]}
                maxBarSize={20}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
