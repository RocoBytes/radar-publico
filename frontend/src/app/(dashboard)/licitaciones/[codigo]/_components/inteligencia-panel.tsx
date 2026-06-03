"use client"

import { useQuery } from "@tanstack/react-query"
import { AlertTriangle, Building2, CheckCircle2, FileText, ShieldAlert, TrendingUp, Trophy, Users, XCircle } from "lucide-react"
import { getInadmisibilidad, getLicitacionInteligencia } from "@/lib/api"
import type { InadmisibilidadData, ItemAdmisibilidad, NivelRiesgo, TopProveedor } from "@/types/inteligencia"
import { Badge } from "@/components/ui/badge"
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

const RIESGO_CONFIG: Record<NivelRiesgo, { label: string; className: string; icon: React.ElementType }> = {
  bajo: { label: "Riesgo bajo", className: "border-green-200 text-green-700 bg-green-50", icon: CheckCircle2 },
  medio: { label: "Riesgo medio", className: "border-yellow-200 text-yellow-700 bg-yellow-50", icon: AlertTriangle },
  alto: { label: "Riesgo alto", className: "border-red-200 text-red-700 bg-red-50", icon: XCircle },
}

const TIPO_ICON: Record<ItemAdmisibilidad["tipo"], React.ElementType> = {
  restriccion: XCircle,
  documento: FileText,
  requisito: ShieldAlert,
}

const TIPO_LABEL: Record<ItemAdmisibilidad["tipo"], string> = {
  restriccion: "Restricción",
  documento: "Documento",
  requisito: "Requisito técnico",
}

function AdmisibilidadCard({ data }: { data: InadmisibilidadData }) {
  if (!data.analisis_disponible) {
    return (
      <Card className="sm:col-span-2">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <ShieldAlert className="h-4 w-4" />
            Verificación de admisibilidad
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Ejecutá el análisis IA de las bases para ver los factores de riesgo de inadmisibilidad.
          </p>
        </CardContent>
      </Card>
    )
  }

  const nivel = data.nivel_riesgo!
  const config = RIESGO_CONFIG[nivel]
  const RiesgoIcon = config.icon

  return (
    <Card className="sm:col-span-2">
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between gap-2 text-sm font-medium text-muted-foreground">
          <span className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" />
            Verificación de admisibilidad
          </span>
          <Badge variant="outline" className={`flex items-center gap-1 ${config.className}`}>
            <RiesgoIcon className="h-3 w-3" />
            {config.label}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {data.resumen && (
          <p className="text-sm text-muted-foreground">{data.resumen}</p>
        )}
        {data.items.length > 0 && (
          <ul className="space-y-2">
            {data.items.map((item, i) => {
              const Icon = TIPO_ICON[item.tipo]
              const colorIcon =
                item.urgencia === "alta"
                  ? "text-red-500"
                  : item.urgencia === "media"
                    ? "text-yellow-500"
                    : "text-blue-500"
              return (
                <li key={i} className="flex items-start gap-2 text-sm">
                  <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${colorIcon}`} />
                  <div className="min-w-0">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide mr-1.5">
                      {TIPO_LABEL[item.tipo]}
                    </span>
                    <span className="leading-snug">{item.descripcion}</span>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        {data.items.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No se detectaron barreras formales en las bases.
          </p>
        )}
      </CardContent>
    </Card>
  )
}

interface InteligenciaPanelProps {
  codigo: string
}

function ProveedorList({ proveedores }: { proveedores: TopProveedor[] }) {
  if (proveedores.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Sin datos de adjudicaciones</p>
    )
  }
  return (
    <ol className="space-y-1.5">
      {proveedores.map((p, i) => (
        <li key={p.rut} className="flex items-start gap-2 text-sm">
          <span className="w-4 shrink-0 text-xs text-muted-foreground font-mono mt-0.5">
            {i + 1}.
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium leading-tight">{p.razon_social}</p>
            <p className="text-xs text-muted-foreground">
              {p.licitaciones_ganadas} licitación{p.licitaciones_ganadas !== 1 ? "es" : ""}
              {p.monto_total !== null && ` · ${formatMonto(p.monto_total)}`}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}

export function InteligenciaPanel({ codigo }: InteligenciaPanelProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["inteligencia", codigo],
    queryFn: () => getLicitacionInteligencia(codigo),
  })

  const { data: inadmisibilidad, isLoading: isLoadingAdmis } = useQuery({
    queryKey: ["inadmisibilidad", codigo],
    queryFn: () => getInadmisibilidad(codigo),
  })

  if (isLoading) {
    return (
      <div className="grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-32 w-full sm:col-span-2" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (!data) return null

  const hayPreciosReales = data.precio_min_organismo !== null || data.precio_max_organismo !== null

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {/* Card: Admisibilidad (ancho completo, siempre visible) */}
      {isLoadingAdmis ? (
        <Skeleton className="h-32 w-full sm:col-span-2" />
      ) : inadmisibilidad ? (
        <AdmisibilidadCard data={inadmisibilidad} />
      ) : null}
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
            <span className="text-muted-foreground">Monto estimado promedio</span>
            <span className="font-semibold">{formatMonto(data.monto_promedio_organismo)}</span>
          </div>
          {data.proveedores_unicos_organismo > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Proveedores distintos</span>
              <span className="font-semibold">{data.proveedores_unicos_organismo}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Card: Rango de precios reales adjudicados */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <TrendingUp className="h-4 w-4" />
            Precios adjudicados reales
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {hayPreciosReales ? (
            <>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Mínimo adjudicado</span>
                <span className="font-semibold text-green-700">
                  {formatMonto(data.precio_min_organismo)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Máximo adjudicado</span>
                <span className="font-semibold text-red-700">
                  {formatMonto(data.precio_max_organismo)}
                </span>
              </div>
              <p className="text-xs text-muted-foreground pt-1">
                Basado en adjudicaciones reales del organismo (últimos 2 años)
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Sin datos de adjudicaciones aún. Se completará automáticamente a medida
              que el sistema sincronice licitaciones adjudicadas.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Card: Top proveedores del organismo */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Trophy className="h-4 w-4" />
            Top proveedores ganadores
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ProveedorList proveedores={data.top_proveedores} />
        </CardContent>
      </Card>

      {/* Card: Competidores en el mismo rubro UNSPSC */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Users className="h-4 w-4" />
            Competidores en tu rubro
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.top_competidores_rubro.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {data.top_proveedores.length === 0
                ? "Sin datos de adjudicaciones aún."
                : "Sin adjudicaciones en este rubro UNSPSC aún."}
            </p>
          ) : (
            <ProveedorList proveedores={data.top_competidores_rubro} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
