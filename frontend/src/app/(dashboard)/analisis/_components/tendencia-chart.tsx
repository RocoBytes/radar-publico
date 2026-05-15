"use client"

import { useQuery } from "@tanstack/react-query"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardTendencia } from "@/lib/api"

function formatMes(mes: string): string {
  try {
    const date = new Date(`${mes}-01`)
    return format(date, "MMM ''yy", { locale: es })
  } catch {
    return mes
  }
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
  name: string
  value: number
  payload: { mes: string; cantidad: number; monto_total: number | null }
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
    <div className="rounded-lg border bg-white px-3 py-2 shadow-lg">
      <p className="text-xs font-medium text-foreground">{formatMes(d.mes)}</p>
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

export function TendenciaChart() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-tendencia", 12],
    queryFn: () => getDashboardTendencia(12),
  })

  const datos = (data?.datos ?? []).map((d) => ({
    ...d,
    mesLabel: formatMes(d.mes),
  }))

  return (
    <Card>
      <CardHeader>
        <CardTitle>Tendencia mensual</CardTitle>
        <CardDescription>Licitaciones publicadas por mes (últimos 12 meses)</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-[300px] w-full" />
        ) : datos.length === 0 ? (
          <div className="flex h-[300px] items-center justify-center">
            <p className="text-sm text-muted-foreground">
              No hay datos de tendencia disponibles
            </p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={datos} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="gradientPrimary" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(226 71% 40%)" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="hsl(226 71% 40%)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(220 20% 88%)" vertical={false} />
              <XAxis
                dataKey="mesLabel"
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={{ stroke: "hsl(220 20% 88%)" }}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11, fill: "hsl(215 16% 47%)" }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ stroke: "hsl(220 20% 88%)" }} />
              <Area
                type="monotone"
                dataKey="cantidad"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                fill="url(#gradientPrimary)"
                dot={{ r: 3, fill: "hsl(var(--primary))", strokeWidth: 0 }}
                activeDot={{ r: 5, fill: "hsl(var(--primary))" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
