"use client"

import { useState, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { getPreferencias, updatePreferencias } from "@/lib/api"
import type { EmailFrecuencia } from "@/types/preferencias"

const TIPOS_OPCIONES: { valor: string; label: string }[] = [
  { valor: "nueva_oportunidad", label: "Nueva oportunidad relevante" },
  { valor: "recordatorio_cierre", label: "Recordatorio de cierre (24h antes)" },
  { valor: "cambio_estado_pipeline", label: "Cambio de estado en pipeline" },
  { valor: "adjudicacion_publicada", label: "Adjudicación publicada" },
  { valor: "oportunidad_futura", label: "Oportunidad futura detectada" },
]

const FRECUENCIAS: { valor: EmailFrecuencia; label: string }[] = [
  { valor: "instantaneo", label: "Inmediatamente" },
  { valor: "diario", label: "Resumen diario (8 AM)" },
  { valor: "semanal", label: "Resumen semanal (lunes 8 AM)" },
]

interface Props {
  onComplete: () => void
  completing: boolean
}

/**
 * Paso 4 del onboarding: preferencias de notificación.
 * Al hacer submit actualiza las preferencias y luego el wizard marca
 * el onboarding como completado.
 */
export function StepNotificaciones({ onComplete, completing }: Props) {
  const [frecuencia, setFrecuencia] = useState<EmailFrecuencia>("instantaneo")
  const [scoreMinimo, setScoreMinimo] = useState<number>(70)
  const [tiposActivos, setTiposActivos] = useState<string[]>(
    TIPOS_OPCIONES.map((t) => t.valor)
  )
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: preferencias } = useQuery({
    queryKey: ["preferencias"],
    queryFn: getPreferencias,
  })

  // Pre-poblar con valores actuales cuando llegan
  useEffect(() => {
    if (!preferencias) return
    setFrecuencia(preferencias.email_frecuencia)
    setScoreMinimo(preferencias.email_score_minimo ?? 70)
    setTiposActivos(preferencias.tipos_activos)
  }, [preferencias])

  function toggleTipo(valor: string) {
    setTiposActivos((prev) =>
      prev.includes(valor) ? prev.filter((t) => t !== valor) : [...prev, valor]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await updatePreferencias({
        email_frecuencia: frecuencia,
        email_score_minimo: scoreMinimo,
        tipos_activos: tiposActivos,
      })
      onComplete()
    } catch {
      setError("No se pudieron guardar las preferencias. Intentá de nuevo.")
      setSaving(false)
    }
  }

  const isDisabled = saving || completing

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Notificaciones</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Configurá cómo y cuándo querés recibir alertas sobre licitaciones.
        </p>
      </div>

      {/* Frecuencia de email */}
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Frecuencia de email</legend>
        <div className="space-y-2">
          {FRECUENCIAS.map(({ valor, label }) => (
            <label key={valor} className="flex cursor-pointer items-center gap-2.5">
              <input
                type="radio"
                name="email_frecuencia"
                value={valor}
                checked={frecuencia === valor}
                onChange={() => setFrecuencia(valor)}
                disabled={isDisabled}
                className="h-4 w-4 accent-primary"
              />
              <span className="text-sm">{label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Score mínimo */}
      <div className="space-y-1.5">
        <Label htmlFor="score_minimo">
          Solo notificarme si el score es ≥{" "}
          <span className="font-semibold text-primary">{scoreMinimo}</span>
        </Label>
        <p className="text-xs text-muted-foreground">
          Usamos un score de relevancia de 0 a 100. El default de 70 filtra el
          ruido y mantiene solo las oportunidades más alineadas a tus rubros.
        </p>
        <div className="flex items-center gap-3">
          <input
            id="score_minimo"
            type="range"
            min={0}
            max={100}
            step={5}
            value={scoreMinimo}
            onChange={(e) => setScoreMinimo(parseInt(e.target.value, 10))}
            disabled={isDisabled}
            className="h-2 w-full cursor-pointer appearance-none rounded-lg bg-muted accent-primary"
          />
          <Input
            type="number"
            min={0}
            max={100}
            value={scoreMinimo}
            onChange={(e) =>
              setScoreMinimo(
                Math.max(0, Math.min(100, parseInt(e.target.value || "0", 10)))
              )
            }
            disabled={isDisabled}
            className="w-20 text-center"
          />
        </div>
      </div>

      {/* Tipos activos */}
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Tipos de notificación activos</legend>
        <div className="space-y-2">
          {TIPOS_OPCIONES.map(({ valor, label }) => (
            <label key={valor} className="flex cursor-pointer items-center gap-2.5">
              <input
                type="checkbox"
                checked={tiposActivos.includes(valor)}
                onChange={() => toggleTipo(valor)}
                disabled={isDisabled}
                className="h-4 w-4 rounded accent-primary"
              />
              <span className="text-sm">{label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={isDisabled}>
          {saving || completing ? "Finalizando…" : "Finalizar configuración"}
        </Button>
      </div>
    </form>
  )
}
