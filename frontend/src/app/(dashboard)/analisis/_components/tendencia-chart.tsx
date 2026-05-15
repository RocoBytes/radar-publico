"use client"

import { useQuery } from "@tanstack/react-query"
import {
  LineChart,
  Line,
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
    <div className="rounded-md border bg-white px-3 py-2 text-sm shadow-md">
      <p className="font-medium">{formatMes(d.mes)}</p>
      <p className="text-muted-foreground">
        {d.cantidad} licitacion{d.cantidad !== 1 ? "es" : ""}
      </p>
      {d.monto_total !== null && (
        <p className="text-muted-foreground">
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
            <LineChart data={datos}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="mesLabel"
                tick={{ fontSize: 11 }}
                interval="preserveStartEnd"
              />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip content={<CustomTooltip />} />
              <Line
                type="monotone"
                dataKey="cantidad"
                stroke="hsl(var(--primary))"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </CardContent>
    </Card>
  )
}
