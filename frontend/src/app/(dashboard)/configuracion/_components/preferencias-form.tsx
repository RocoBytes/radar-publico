"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { getPreferencias, updatePreferencias } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import {
  Form,
  FormControl,
  FormDescription,
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

const preferenciasSchema = z.object({
  email_activo: z.boolean(),
  email_frecuencia: z.enum(["instantaneo", "diario", "semanal"]),
  email_score_minimo: z.coerce
    .number()
    .min(0)
    .max(100)
    .nullable()
    .optional(),
  in_app_activo: z.boolean(),
  whatsapp_activo: z.boolean(),
  whatsapp_solo_criticas: z.boolean(),
  whatsapp_score_minimo: z.coerce
    .number()
    .min(0)
    .max(100)
    .nullable()
    .optional(),
})

type PreferenciasFormValues = z.infer<typeof preferenciasSchema>

export function PreferenciasForm() {
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ["preferencias-notificaciones"],
    queryFn: getPreferencias,
  })

  const form = useForm<PreferenciasFormValues>({
    resolver: zodResolver(preferenciasSchema),
    defaultValues: {
      email_activo: true,
      email_frecuencia: "diario",
      email_score_minimo: null,
      in_app_activo: true,
      whatsapp_activo: false,
      whatsapp_solo_criticas: false,
      whatsapp_score_minimo: null,
    },
  })

  useEffect(() => {
    if (data) {
      form.reset({
        email_activo: data.email_activo,
        email_frecuencia: data.email_frecuencia,
        email_score_minimo: data.email_score_minimo,
        in_app_activo: data.in_app_activo,
        whatsapp_activo: data.whatsapp_activo,
        whatsapp_solo_criticas: data.whatsapp_solo_criticas,
        whatsapp_score_minimo: data.whatsapp_score_minimo,
      })
    }
  }, [data, form])

  const { mutate, isPending } = useMutation({
    mutationFn: updatePreferencias,
    onSuccess: () => {
      toast.success("Preferencias guardadas correctamente")
      void queryClient.invalidateQueries({
        queryKey: ["preferencias-notificaciones"],
      })
    },
    onError: () => {
      toast.error("No se pudieron guardar las preferencias")
    },
  })

  function onSubmit(values: PreferenciasFormValues) {
    mutate({
      email_activo: values.email_activo,
      email_frecuencia: values.email_frecuencia,
      email_score_minimo: values.email_score_minimo ?? null,
      in_app_activo: values.in_app_activo,
      whatsapp_activo: values.whatsapp_activo,
      whatsapp_solo_criticas: values.whatsapp_solo_criticas,
      whatsapp_score_minimo: values.whatsapp_score_minimo ?? null,
    })
  }

  const whatsappActivo = form.watch("whatsapp_activo")

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Preferencias de notificaciones</CardTitle>
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
        <CardTitle>Preferencias de notificaciones</CardTitle>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
            {/* Sección Email */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">Email</h3>

              <FormField
                control={form.control}
                name="email_activo"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel className="text-sm">
                        Notificaciones por email
                      </FormLabel>
                      <FormDescription className="text-xs">
                        Recibí alertas de nuevas licitaciones por correo
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email_frecuencia"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Frecuencia</FormLabel>
                    <Select
                      onValueChange={field.onChange}
                      value={field.value}
                      disabled={!form.watch("email_activo")}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="instantaneo">Instantáneo</SelectItem>
                        <SelectItem value="diario">
                          Resumen diario (8 AM)
                        </SelectItem>
                        <SelectItem value="semanal">
                          Resumen semanal (lunes)
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="email_score_minimo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Score mínimo (0–100)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        placeholder="Sin mínimo"
                        disabled={!form.watch("email_activo")}
                        value={field.value ?? ""}
                        onChange={(e) =>
                          field.onChange(
                            e.target.value === ""
                              ? null
                              : Number(e.target.value)
                          )
                        }
                      />
                    </FormControl>
                    <FormDescription className="text-xs">
                      Solo se notifica si el score de relevancia supera este
                      umbral
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <Separator />

            {/* Sección In-App */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">En la aplicación</h3>

              <FormField
                control={form.control}
                name="in_app_activo"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel className="text-sm">
                        Notificaciones en la aplicación
                      </FormLabel>
                      <FormDescription className="text-xs">
                        Alertas en tiempo real dentro de Radar Público
                        (recomendado)
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />
            </div>

            <Separator />

            {/* Sección WhatsApp */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">WhatsApp</h3>

              <FormField
                control={form.control}
                name="whatsapp_activo"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel className="text-sm">
                        Notificaciones por WhatsApp
                      </FormLabel>
                      <FormDescription className="text-xs">
                        Recibí alertas directamente en WhatsApp
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="whatsapp_solo_criticas"
                render={({ field }) => (
                  <FormItem className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <FormLabel
                        className={`text-sm ${!whatsappActivo ? "text-muted-foreground" : ""}`}
                      >
                        Solo críticas
                      </FormLabel>
                      <FormDescription className="text-xs">
                        Solo notificaciones de alta prioridad
                      </FormDescription>
                    </div>
                    <FormControl>
                      <Switch
                        checked={field.value}
                        onCheckedChange={field.onChange}
                        disabled={!whatsappActivo}
                      />
                    </FormControl>
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="whatsapp_score_minimo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Score mínimo WhatsApp (0–100)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        placeholder="Sin mínimo"
                        disabled={!whatsappActivo}
                        value={field.value ?? ""}
                        onChange={(e) =>
                          field.onChange(
                            e.target.value === ""
                              ? null
                              : Number(e.target.value)
                          )
                        }
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <div className="flex justify-end pt-2">
              <Button type="submit" disabled={isPending}>
                {isPending ? "Guardando…" : "Guardar preferencias"}
              </Button>
            </div>
          </form>
        </Form>
      </CardContent>
    </Card>
  )
}
