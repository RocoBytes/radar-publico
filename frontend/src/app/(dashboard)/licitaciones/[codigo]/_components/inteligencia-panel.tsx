"use client"

import { useQuery } from "@tanstack/react-query"
import { Building2, Trophy } from "lucide-react"
import { getLicitacionInteligencia } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

function formatMonto(monto: number | null): string {
  if (monto === null) return "—"
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(monto)
}

interface InteligenciaPanelProps {
  codigo: string
}

export function InteligenciaPanel({ codigo }: InteligenciaPanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["inteligencia", codigo],
    queryFn: () => getLicitacionInteligencia(codigo),
  })

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Card: Histórico del organismo */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Building2 className="h-4 w-4" />
            {data.organismo_nombre ?? "Organismo"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Licitaciones (2 años)</span>
            <span className="font-semibold">{data.total_licitaciones_organismo}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Monto promedio</span>
            <span className="font-semibold">{formatMonto(data.monto_promedio_organismo)}</span>
          </div>
        </CardContent>
      </Card>

      {/* Card: Top proveedores */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Trophy className="h-4 w-4" />
            Top proveedores ganadores
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.top_proveedores.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin datos de adjudicaciones</p>
          ) : (
            <ol className="space-y-1.5">
              {data.top_proveedores.map((p, i) => (
                <li key={p.rut} className="flex items-start gap-2 text-sm">
                  <span className="w-4 shrink-0 text-xs text-muted-foreground font-mono mt-0.5">
                    {i + 1}.
                  </span>
                  <div className="min-w-0">
                    <p className="truncate font-medium leading-tight">{p.razon_social}</p>
                    <p className="text-xs text-muted-foreground">
                      {p.licitaciones_ganadas} licitación{p.licitaciones_ganadas !== 1 ? "es" : ""}{" "}
                      {p.monto_total !== null && `· ${formatMonto(p.monto_total)}`}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
