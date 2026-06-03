"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getEmpresaMe, updateEmpresaMe } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const empresaSchema = z.object({
  nombre_fantasia: z.string().max(200).nullable().optional(),
  tamano: z
    .enum(["micro", "pequena", "mediana", "grande"])
    .nullable()
    .optional(),
  contacto_telefono: z.string().max(50).nullable().optional(),
  contacto_direccion: z.string().max(500).nullable().optional(),
  giros_texto: z.string().optional(),
})

type EmpresaFormValues = z.infer<typeof empresaSchema>

const TAMANO_LABELS: Record<string, string> = {
  micro: "Micro (1–9 empleados)",
  pequena: "Pequeña (10–49 empleados)",
  mediana: "Mediana (50–199 empleados)",
  grande: "Grande (200+ empleados)",
}

export function EmpresaForm() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["empresa-me"],
    queryFn: getEmpresaMe,
  })

  const form = useForm<EmpresaFormValues>({
    resolver: zodResolver(empresaSchema),
    defaultValues: {
      nombre_fantasia: "",
      tamano: undefined,
      contacto_telefono: "",
      contacto_direccion: "",
      giros_texto: "",
    },
  })

  useEffect(() => {
    if (data) {
      form.reset({
        nombre_fantasia: data.nombre_fantasia ?? "",
        tamano: data.tamano ?? undefined,
        contacto_telefono: data.contacto_telefono ?? "",
        contacto_direccion: data.contacto_direccion ?? "",
        giros_texto: (data.giros ?? []).join("\n"),
      })
    }
  }, [data, form])

  const { mutate, isPending } = useMutation({
    mutationFn: updateEmpresaMe,
    onSuccess: () => {
      toast.success("Datos guardados correctamente")
      void queryClient.invalidateQueries({ queryKey: ["empresa-me"] })
    },
    onError: () => {
      toast.error("No se pudieron guardar los cambios")
    },
  })

  function onSubmit(values: EmpresaFormValues) {
    const giros = (values.giros_texto ?? "")
      .split("\n")
      .map((g) => g.trim())
      .filter(Boolean)

    mutate({
      nombre_fantasia: values.nombre_fantasia ?? null,
      tamano: values.tamano ?? null,
      contacto_telefono: values.contacto_telefono ?? null,
      contacto_direccion: values.contacto_direccion ?? null,
      giros: giros.length > 0 ? giros : null,
    })
  }

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Datos de la empresa</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Datos de la empresa</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Campos de solo lectura */}
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <p className="text-sm font-medium leading-none">RUT</p>
            <div className="flex h-9 items-center rounded-md border border-border bg-muted/50 px-3 text-sm text-muted-foreground">
              {data?.rut ?? "—"}
            </div>
          </div>
          <div className="space-y-1.5">
            <p className="text-sm font-medium leading-none">Razón social</p>
            <div className="flex h-9 items-center rounded-md border border-border bg-muted/50 px-3 text-sm text-muted-foreground">
              {data?.razon_social ?? "—"}
            </div>
          </div>
        </div>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="nombre_fantasia"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre de fantasía</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Nombre comercial (opcional)"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="tamano"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Tamaño de empresa</FormLabel>
                  <Select
                    onValueChange={(v: string) =>
                      field.onChange(
                        v === "none"
                          ? null
                          : (v as "micro" | "pequena" | "mediana" | "grande")
                      )
                    }
                    value={field.value ?? "none"}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Seleccionar tamaño" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="none">Sin especificar</SelectItem>
                      {Object.entries(TAMANO_LABELS).map(([value, label]) => (
                        <SelectItem key={value} value={value}>
                          {label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="contacto_telefono"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Teléfono de contacto</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="+56 9 1234 5678"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="contacto_direccion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Dirección</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Av. Ejemplo 123, Santiago"
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="giros_texto"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Rubros / giros</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Un rubro por línea&#10;Ej: Tecnología&#10;Servicios de consultoría"
                      rows={4}
                      {...field}
                      value={field.value ?? ""}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={isPending}>
                {isPending ? "Guardando…" : "Guardar cambios"}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
