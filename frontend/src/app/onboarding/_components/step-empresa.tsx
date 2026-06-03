"use client"

import { useState, useEffect } from "react"
import { useForm, Controller } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useQuery } from "@tanstack/react-query"
import { X, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { getCatalogosRegiones, getEmpresaMe, updateEmpresaMe } from "@/lib/api"
import type { EmpresaTamano } from "@/types/empresa"

const empresaSchema = z.object({
  nombre_fantasia: z.string().max(200).optional().or(z.literal("")),
  giros: z.array(z.string()).optional(),
  tamano: z
    .enum(["micro", "pequena", "mediana", "grande"] as const)
    .optional()
    .nullable(),
  ano_fundacion: z
    .number()
    .int()
    .min(1900)
    .max(2026)
    .optional()
    .nullable(),
  numero_empleados: z.number().int().min(0).optional().nullable(),
  regiones_operacion: z
    .array(z.string())
    .min(1, "Seleccioná al menos una región"),
  sello_empresa_mujer: z.boolean(),
  inscrito_chileproveedores: z.boolean(),
})

type EmpresaFormValues = z.infer<typeof empresaSchema>

interface Props {
  onNext: () => void
}

/**
 * Paso 1 del onboarding: datos básicos de la empresa.
 * Pre-popula con los valores actuales desde /empresa/me.
 */
export function StepEmpresa({ onNext }: Props) {
  const [giroInput, setGiroInput] = useState("")
  const [serverError, setServerError] = useState<string | null>(null)

  const { data: empresa, isLoading: loadingEmpresa } = useQuery({
    queryKey: ["empresa-me"],
    queryFn: getEmpresaMe,
  })

  const { data: regionesData, isLoading: loadingRegiones } = useQuery({
    queryKey: ["catalogos-regiones"],
    queryFn: getCatalogosRegiones,
  })

  const form = useForm<EmpresaFormValues>({
    resolver: zodResolver(empresaSchema),
    defaultValues: {
      nombre_fantasia: "",
      giros: [],
      tamano: null,
      ano_fundacion: null,
      numero_empleados: null,
      regiones_operacion: [],
      sello_empresa_mujer: false,
      inscrito_chileproveedores: false,
    },
  })

  // Pre-poblar con datos actuales cuando llegan
  useEffect(() => {
    if (!empresa) return
    form.reset({
      nombre_fantasia: empresa.nombre_fantasia ?? "",
      giros: empresa.giros ?? [],
      tamano: empresa.tamano ?? null,
      ano_fundacion: empresa.ano_fundacion ?? null,
      numero_empleados: empresa.numero_empleados ?? null,
      regiones_operacion: empresa.regiones_operacion ?? [],
      sello_empresa_mujer: empresa.sello_empresa_mujer ?? false,
      inscrito_chileproveedores: empresa.inscrito_chileproveedores ?? false,
    })
  }, [empresa, form])

  const giros = form.watch("giros") ?? []
  const regionesSeleccionadas = form.watch("regiones_operacion") ?? []

  function agregarGiro() {
    const val = giroInput.trim()
    if (!val || giros.includes(val)) return
    form.setValue("giros", [...giros, val])
    setGiroInput("")
  }

  function eliminarGiro(giro: string) {
    form.setValue(
      "giros",
      giros.filter((g) => g !== giro)
    )
  }

  function toggleRegion(codigo: string) {
    const current = regionesSeleccionadas
    if (current.includes(codigo)) {
      form.setValue(
        "regiones_operacion",
        current.filter((r) => r !== codigo),
        { shouldValidate: true }
      )
    } else {
      form.setValue("regiones_operacion", [...current, codigo], {
        shouldValidate: true,
      })
    }
  }

  async function onSubmit(values: EmpresaFormValues) {
    setServerError(null)
    try {
      await updateEmpresaMe({
        nombre_fantasia: values.nombre_fantasia || null,
        giros: values.giros,
        tamano: (values.tamano as EmpresaTamano) ?? null,
        ano_fundacion: values.ano_fundacion ?? null,
        numero_empleados: values.numero_empleados ?? null,
        regiones_operacion: values.regiones_operacion,
        sello_empresa_mujer: values.sello_empresa_mujer,
        inscrito_chileproveedores: values.inscrito_chileproveedores,
      })
      onNext()
    } catch {
      setServerError("No se pudo guardar. Intentá de nuevo.")
    }
  }

  const isLoading = loadingEmpresa || loadingRegiones
  const isSubmitting = form.formState.isSubmitting

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Tu empresa</h2>
        <p className="text-sm text-muted-foreground">
          Completá los datos básicos de tu empresa.
        </p>
      </div>

      {/* Nombre de fantasía */}
      <div className="space-y-1.5">
        <Label htmlFor="nombre_fantasia">Nombre de fantasía</Label>
        <Input
          id="nombre_fantasia"
          placeholder="Ej: MiEmpresa Ltda."
          disabled={isLoading || isSubmitting}
          {...form.register("nombre_fantasia")}
        />
        {form.formState.errors.nombre_fantasia && (
          <p className="text-sm text-destructive">
            {form.formState.errors.nombre_fantasia.message}
          </p>
        )}
      </div>

      {/* Giros */}
      <div className="space-y-1.5">
        <Label>Giro(s) de la empresa</Label>
        <div className="flex gap-2">
          <Input
            value={giroInput}
            onChange={(e) => setGiroInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault()
                agregarGiro()
              }
            }}
            placeholder="Ej: Servicios de limpieza"
            disabled={isLoading || isSubmitting}
          />
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={agregarGiro}
            disabled={isLoading || isSubmitting}
            aria-label="Agregar giro"
          >
            <Plus className="h-4 w-4" />
          </Button>
        </div>
        {giros.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {giros.map((giro) => (
              <Badge
                key={giro}
                variant="secondary"
                className="flex items-center gap-1"
              >
                {giro}
                <button
                  type="button"
                  onClick={() => eliminarGiro(giro)}
                  className="ml-1 rounded-full hover:text-destructive"
                  aria-label={`Eliminar giro ${giro}`}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Tamaño */}
      <div className="space-y-1.5">
        <Label>Tamaño</Label>
        <Controller
          control={form.control}
          name="tamano"
          render={({ field }) => (
            <Select
              value={field.value ?? ""}
              onValueChange={(v) =>
                field.onChange(v === "" ? null : (v as EmpresaTamano))
              }
              disabled={isLoading || isSubmitting}
            >
              <SelectTrigger>
                <SelectValue placeholder="Seleccioná el tamaño" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="micro">Micro</SelectItem>
                <SelectItem value="pequena">Pequeña</SelectItem>
                <SelectItem value="mediana">Mediana</SelectItem>
                <SelectItem value="grande">Grande</SelectItem>
              </SelectContent>
            </Select>
          )}
        />
      </div>

      {/* Año de fundación */}
      <div className="space-y-1.5">
        <Label htmlFor="ano_fundacion">Año de fundación</Label>
        <Input
          id="ano_fundacion"
          type="number"
          min={1900}
          max={2026}
          placeholder="Ej: 2010"
          disabled={isLoading || isSubmitting}
          {...form.register("ano_fundacion", {
            setValueAs: (v) =>
              v === "" || v === null ? null : parseInt(v as string, 10),
          })}
        />
        {form.formState.errors.ano_fundacion && (
          <p className="text-sm text-destructive">
            {form.formState.errors.ano_fundacion.message}
          </p>
        )}
      </div>

      {/* Número de empleados */}
      <div className="space-y-1.5">
        <Label htmlFor="numero_empleados">N° de empleados aproximado</Label>
        <Input
          id="numero_empleados"
          type="number"
          min={0}
          placeholder="Ej: 25"
          disabled={isLoading || isSubmitting}
          {...form.register("numero_empleados", {
            setValueAs: (v) =>
              v === "" || v === null ? null : parseInt(v as string, 10),
          })}
        />
        {form.formState.errors.numero_empleados && (
          <p className="text-sm text-destructive">
            {form.formState.errors.numero_empleados.message}
          </p>
        )}
      </div>

      {/* Regiones de operación */}
      <div className="space-y-1.5">
        <Label>
          Regiones donde opera{" "}
          <span className="text-muted-foreground">(mínimo 1)</span>
        </Label>
        {loadingRegiones ? (
          <p className="text-sm text-muted-foreground">Cargando regiones…</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 rounded-md border p-3 sm:grid-cols-3">
            {(regionesData?.items ?? []).map((region) => {
              const checked = regionesSeleccionadas.includes(region.codigo)
              return (
                <label
                  key={region.codigo}
                  className="flex cursor-pointer items-center gap-2 text-sm"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleRegion(region.codigo)}
                    disabled={isSubmitting}
                    className="h-4 w-4 rounded border-input accent-primary"
                  />
                  <span className="leading-tight">{region.nombre}</span>
                </label>
              )
            })}
          </div>
        )}
        {form.formState.errors.regiones_operacion && (
          <p className="text-sm text-destructive">
            {form.formState.errors.regiones_operacion.message}
          </p>
        )}
      </div>

      {/* Sello empresa mujer */}
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
          disabled={isSubmitting}
          {...form.register("sello_empresa_mujer")}
        />
        <div>
          <span className="text-sm font-medium">Sello Empresa Mujer</span>
          <p className="text-xs text-muted-foreground">
            Mi empresa tiene el sello de Empresa Mujer de SERCOTEC
          </p>
        </div>
      </label>

      {/* Inscrito en ChileProveedores */}
      <label className="flex cursor-pointer items-start gap-3">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 rounded border-input accent-primary"
          disabled={isSubmitting}
          {...form.register("inscrito_chileproveedores")}
        />
        <div>
          <span className="text-sm font-medium">Inscrito en ChileProveedores</span>
          <p className="text-xs text-muted-foreground">
            Mi empresa está inscrita y habilitada en el registro de proveedores
          </p>
        </div>
      </label>

      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
      )}

      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading || isSubmitting}>
          {isSubmitting ? "Guardando…" : "Continuar"}
        </Button>
      </div>
    </form>
  )
}
