"use client"

import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { getCatalogosUnspsc, getIntereses, createInteres, deleteInteres } from "@/lib/api"
import type { UnspscSegmento, UnspscFamilia } from "@/types/catalogos"
import type { Interes } from "@/types/intereses"

interface Props {
  onNext: () => void
}

/**
 * Paso 3 del onboarding: selección de intereses UNSPSC y keywords.
 * Requiere al menos 1 interés UNSPSC para avanzar.
 */
export function StepIntereses({ onNext }: Props) {
  const queryClient = useQueryClient()

  // Selecciones temporales del árbol UNSPSC
  const [segmentoCodigo, setSegmentoCodigo] = useState<string>("")
  const [familiaCodigo, setFamiliaCodigo] = useState<string>("")

  // Input de keyword libre
  const [keywordInput, setKeywordInput] = useState("")

  const [addError, setAddError] = useState<string | null>(null)
  const [continueError, setContinueError] = useState<string | null>(null)

  // Carga del catálogo UNSPSC
  const { data: unspscData, isLoading: loadingUnspsc } = useQuery({
    queryKey: ["catalogos-unspsc"],
    queryFn: getCatalogosUnspsc,
  })

  // Carga de intereses actuales
  const { data: interesesData, isLoading: loadingIntereses } = useQuery({
    queryKey: ["intereses"],
    queryFn: getIntereses,
  })

  // Mutación para crear interés
  const crearMutation = useMutation({
    mutationFn: createInteres,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["intereses"] })
      setAddError(null)
    },
    onError: (err: Error) => {
      setAddError(err.message)
    },
  })

  // Mutación para eliminar interés
  const eliminarMutation = useMutation({
    mutationFn: deleteInteres,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["intereses"] })
    },
  })

  const segmentos: UnspscSegmento[] = unspscData?.items ?? []
  const intereses: Interes[] = interesesData?.items ?? []

  // Familias del segmento seleccionado
  const familias: UnspscFamilia[] =
    segmentos.find((s) => s.codigo === segmentoCodigo)?.familias ?? []

  // Al cambiar segmento, limpiar familia
  function handleSegmentoChange(codigo: string) {
    setSegmentoCodigo(codigo)
    setFamiliaCodigo("")
    setAddError(null)
  }

  async function agregarUnspsc() {
    if (!segmentoCodigo) {
      setAddError("Seleccioná un segmento primero.")
      return
    }
    setAddError(null)

    const usaFamilia = familiaCodigo !== "" && familiaCodigo !== "__todo__"

    try {
      await crearMutation.mutateAsync({
        tipo: usaFamilia ? "unspsc_familia" : "unspsc_segmento",
        valor: usaFamilia ? familiaCodigo : segmentoCodigo,
      })
      setSegmentoCodigo("")
      setFamiliaCodigo("")
    } catch {
      // error capturado por onError del mutation → setAddError
    }
  }

  async function agregarKeyword() {
    const val = keywordInput.trim()
    if (!val) return
    setAddError(null)
    try {
      await crearMutation.mutateAsync({
        tipo: "keyword",
        valor: val,
      })
      setKeywordInput("")
    } catch {
      // error capturado por onError del mutation → setAddError
    }
  }

  function handleContinuar() {
    const tieneUnspsc = intereses.some(
      (i) =>
        i.tipo === "unspsc_segmento" ||
        i.tipo === "unspsc_familia" ||
        i.tipo === "unspsc_clase" ||
        i.tipo === "unspsc_commodity"
    )
    if (!tieneUnspsc) {
      setContinueError("Agregá al menos un rubro UNSPSC antes de continuar.")
      return
    }
    setContinueError(null)
    onNext()
  }

  const isLoading = loadingUnspsc || loadingIntereses
  const isMutating = crearMutation.isPending || eliminarMutation.isPending

  // Etiqueta legible para un interés
  function etiquetaInteres(interes: Interes): string {
    if (interes.tipo === "keyword") return `🔑 ${interes.valor}`
    if (interes.tipo === "unspsc_segmento") {
      const seg = segmentos.find((s) => s.codigo === interes.valor)
      return `${interes.valor} — ${seg?.nombre ?? interes.valor}`
    }
    if (interes.tipo === "unspsc_familia") {
      for (const seg of segmentos) {
        const fam = seg.familias.find((f) => f.codigo === interes.valor)
        if (fam) return `${interes.valor} — ${fam.nombre}`
      }
    }
    return interes.valor
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Mis intereses</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Indicá los rubros de licitaciones que te interesan. Usamos esto para
          filtrarte las oportunidades más relevantes.
        </p>
      </div>

      {/* Selector UNSPSC */}
      <div className="space-y-3">
        <Label>Agregar rubro UNSPSC</Label>

        <div className="flex flex-col gap-2 sm:flex-row">
          {/* Segmento */}
          <div className="flex-1">
            <Select
              value={segmentoCodigo}
              onValueChange={handleSegmentoChange}
              disabled={isLoading || isMutating}
            >
              <SelectTrigger>
                <SelectValue placeholder="Seleccioná un segmento…" />
              </SelectTrigger>
              <SelectContent>
                {segmentos.map((seg) => (
                  <SelectItem key={seg.codigo} value={seg.codigo}>
                    {seg.codigo} — {seg.nombre}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Familia (solo si hay segmento seleccionado) */}
          {segmentoCodigo && (
            <div className="flex-1">
              <Select
                value={familiaCodigo}
                onValueChange={setFamiliaCodigo}
                disabled={isLoading || isMutating}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Todo el segmento" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__todo__">Todo el segmento</SelectItem>
                  {familias.map((fam) => (
                    <SelectItem key={fam.codigo} value={fam.codigo}>
                      {fam.codigo} — {fam.nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          <Button
            type="button"
            onClick={agregarUnspsc}
            disabled={!segmentoCodigo || isLoading || isMutating}
            className="shrink-0"
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Agregar
          </Button>
        </div>
      </div>

      <Separator />

      {/* Keyword libre */}
      <div className="space-y-2">
        <Label>Agregar palabra clave libre</Label>
        <div className="flex gap-2">
          <Input
            value={keywordInput}
            onChange={(e) => setKeywordInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                void agregarKeyword()
              }
            }}
            placeholder="Ej: aire acondicionado, pintura, consultoría"
            disabled={isLoading || isMutating}
          />
          <Button
            type="button"
            variant="outline"
            onClick={agregarKeyword}
            disabled={!keywordInput.trim() || isLoading || isMutating}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Error de agregar */}
      {addError && (
        <p role="alert" className="text-sm text-destructive">
          {addError}
        </p>
      )}

      {/* Lista de intereses actuales */}
      {isLoading ? (
        <p className="text-sm text-muted-foreground">Cargando…</p>
      ) : intereses.length > 0 ? (
        <div className="space-y-2">
          <Label>Tus intereses actuales</Label>
          <div className="flex flex-wrap gap-2">
            {intereses.map((interes) => (
              <Badge
                key={interes.id}
                variant="secondary"
                className="flex items-center gap-1 py-1 pl-2.5 pr-1.5"
              >
                <span className="max-w-[220px] truncate">
                  {etiquetaInteres(interes)}
                </span>
                <button
                  type="button"
                  onClick={() => eliminarMutation.mutate(interes.id)}
                  disabled={isMutating}
                  className="ml-0.5 rounded-full p-0.5 hover:text-destructive"
                  aria-label={`Eliminar interés ${interes.valor}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Aún no agregaste intereses.
        </p>
      )}

      {/* Error de continuar */}
      {continueError && (
        <p role="alert" className="text-sm text-destructive">
          {continueError}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="button" onClick={handleContinuar} disabled={isMutating}>
          Continuar
        </Button>
      </div>
    </div>
  )
}
