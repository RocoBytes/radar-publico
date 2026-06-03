"use client"

import Link from "next/link"
import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { es } from "date-fns/locale"
import { ChevronRight } from "lucide-react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getDashboardResumen } from "@/lib/api"
import type { TopOportunidad } from "@/types/dashboard"

function scoreCircleClass(score: number | null): string {
  if (score === null) return "bg-muted text-muted-foreground"
  if (score >= 70) return "bg-green-100 text-green-800"
  if (score >= 40) return "bg-amber-100 text-amber-700"
  return "bg-slate-100 text-slate-600"
}

function OportunidadRow({ item }: { item: TopOportunidad }) {
  const fechaCierre = item.licitacion.fecha_cierre
    ? format(new Date(item.licitacion.fecha_cierre), "d MMM", { locale: es })
    : null

  return (
    <Link
      href={`/pipeline/${item.id}`}
      className="group flex cursor-pointer items-center gap-3 rounded-md p-2 transition-colors hover:bg-muted/50"
    >
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${scoreCircleClass(item.score)}`}
      >
        {item.score ?? "—"}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.licitacion.nombre}</p>
        <p className="text-xs text-muted-foreground">
          {item.licitacion.organismo_nombre ?? "—"}
          {fechaCierre ? ` · Cierra ${fechaCierre}` : ""}
        </p>
      </div>
      <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
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
      <CardContent className="space-y-0.5">
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full rounded-md" />
            ))}
          </div>
        ) : top.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Tu pipeline está vacío. Explorá las oportunidades para agregar licitaciones.
          </p>
        ) : (
          top.map((item) => <OportunidadRow key={item.id} item={item} />)
        )}
      </CardContent>
    </Card>
  )
}
