"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardResumen } from "@/lib/api"
import type { TopOportunidad } from "@/types/dashboard"

function scoreBadgeClass(score: number | null): string {
  if (score === null) return "bg-muted text-muted-foreground border-transparent"
  if (score >= 70) return "bg-green-100 text-green-800 border-transparent"
  if (score >= 40) return "bg-yellow-100 text-yellow-800 border-transparent"
  return "bg-muted text-muted-foreground border-transparent"
}

function OportunidadRow({ item }: { item: TopOportunidad }) {
  const fechaCierre = item.licitacion.fecha_cierre
    ? format(new Date(item.licitacion.fecha_cierre), "d MMM", { locale: es })
    : null

  return (
    <Link
      href={`/pipeline/${item.id}`}
      className="flex items-start gap-3 rounded-md p-2 hover:bg-muted/50 transition-colors"
    >
      <Badge className={scoreBadgeClass(item.score)}>
        {item.score ?? "—"}
      </Badge>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.licitacion.nombre}</p>
        <p className="text-xs text-muted-foreground">
          {item.licitacion.organismo_nombre ?? "—"}
          {fechaCierre ? ` · Cierra ${fechaCierre}` : ""}
        </p>
      </div>
    </Link>
  )
}

export function TopOportunidades() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard-resumen"],
    queryFn: getDashboardResumen,
  })

  const top = data?.top_oportunidades?.slice(0, 5) ?? []

  return (
    <Card>
      <CardHeader>
        <CardTitle>Top oportunidades</CardTitle>
        <CardDescription>Por score de relevancia</CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-md" />
            ))}
          </div>
        ) : top.length === 0 ? (
          <p className="py-4 text-center text-sm text-muted-foreground">
            Tu pipeline está vacío. Explorá las oportunidades para agregar licitaciones.
          </p>
        ) : (
          top.map((item) => <OportunidadRow key={item.id} item={item} />)
        )}
      </CardContent>
    </Card>
  )
}
