"use client"

import { Separator } from "@/components/ui/separator"
import type { ScoreJustificacion, ScoreRegionRazon } from "@/types/pipeline"

interface ScoreRowProps {
  label: string
  puntos: number
  max: number
  children: React.ReactNode
}

function ScoreRow({ label, puntos, max, children }: ScoreRowProps) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground">
          {puntos}/{max}
        </span>
      </div>
      <div className="h-2 w-full rounded bg-slate-100 overflow-hidden">
        <div
          style={{ width: `${max > 0 ? Math.round((puntos / max) * 100) : 0}%` }}
          className="h-full bg-primary transition-all"
          role="progressbar"
          aria-valuenow={puntos}
          aria-valuemin={0}
          aria-valuemax={max}
          aria-label={`${label}: ${puntos} de ${max} puntos`}
        />
      </div>
      <div className="text-xs text-muted-foreground">{children}</div>
    </div>
  )
}

const REGION_MENSAJE: Record<ScoreRegionRazon, string> = {
  match: "Coincide con tu región",
  no_match: "Fuera de tu región",
  nacional: "Licitación nacional",
  sin_datos: "Sin datos de región",
}

interface ScoreBreakdownProps {
  justificacion: ScoreJustificacion | null
}

export function ScoreBreakdown({ justificacion }: ScoreBreakdownProps) {
  if (justificacion === null) {
    return (
      <p className="text-sm text-muted-foreground">
        Score pendiente de cálculo. Sin desglose disponible.
      </p>
    )
  }

  const { unspsc, region, keywords, semantico } = justificacion

  return (
    <div className="space-y-4">
      {unspsc !== undefined && (
        <ScoreRow label="Rubro (UNSPSC)" puntos={unspsc.puntos} max={unspsc.max}>
          {unspsc.matches.length > 0 ? (
            <div className="flex flex-wrap gap-1 mt-1">
              {unspsc.matches.map((codigo) => (
                <span
                  key={codigo}
                  className="inline-flex items-center rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-xs"
                >
                  {codigo}
                </span>
              ))}
            </div>
          ) : (
            <span>Sin coincidencias de rubro</span>
          )}
        </ScoreRow>
      )}

      {region !== undefined && (
        <ScoreRow label="Región" puntos={region.puntos} max={region.max}>
          {REGION_MENSAJE[region.razon]}
        </ScoreRow>
      )}

      {keywords !== undefined && (
        <ScoreRow label="Palabras clave" puntos={keywords.puntos} max={keywords.max}>
          {keywords.matches.length > 0 ? (
            <div className="flex flex-wrap gap-1 mt-1">
              {keywords.matches.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center rounded-full bg-slate-100 border border-slate-200 px-2 py-0.5 text-xs"
                >
                  {kw}
                </span>
              ))}
            </div>
          ) : (
            <span>Sin keywords matcheadas</span>
          )}
        </ScoreRow>
      )}

      {semantico !== undefined && (
        <ScoreRow label="Semántico" puntos={semantico.puntos} max={semantico.max}>
          {semantico.similitud !== null
            ? `${Math.round(semantico.similitud * 100)}% de similitud`
            : "No disponible"}
        </ScoreRow>
      )}

      <Separator />

      <p className="text-right font-bold">Total: {justificacion.total}/100</p>
    </div>
  )
}
