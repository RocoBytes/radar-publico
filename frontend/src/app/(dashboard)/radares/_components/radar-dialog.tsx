"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { createRadar, updateRadar } from "@/lib/api"
import type { Radar, NotifCanal } from "@/types/radar"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const radarSchema = z.object({
  nombre: z.string().min(1, "El nombre es obligatorio"),
  descripcion: z.string().optional(),
  filtros_q: z.string().optional(),
  filtros_estado: z.string().optional(),
  notif_canal: z.enum(["email", "whatsapp", "in_app"] as const),
  notif_score_minimo: z
    .number()
    .min(0, "Mínimo 0")
    .max(100, "Máximo 100"),
})

type RadarFormValues = z.infer<typeof radarSchema>

const NOTIF_CANAL_OPCIONES: { value: NotifCanal; label: string }[] = [
  { value: "email", label: "Email" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "in_app", label: "En la app" },
]

const ESTADOS_LICITACION = [
  { value: "publicada", label: "Publicada" },
  { value: "cerrada", label: "Cerrada" },
  { value: "adjudicada", label: "Adjudicada" },
]

interface RadarDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Si se pasa, modo edición; si no, modo creación */
  radar?: Radar
}

export function RadarDialog({ open, onOpenChange, radar }: RadarDialogProps) {
  const queryClient = useQueryClient()
  const esEdicion = Boolean(radar)

  const form = useForm<RadarFormValues>({
    resolver: zodResolver(radarSchema),
    defaultValues: {
      nombre: "",
      descripcion: "",
      filtros_q: "",
      filtros_estado: "",
      notif_canal: "email",
      notif_score_minimo: 0,
    },
  })

  // Poblar formulario al abrir en modo edición
  useEffect(() => {
    if (radar) {
      form.reset({
        nombre: radar.nombre,
        descripcion: radar.descripcion ?? "",
        filtros_q: radar.filtros.q ?? "",
        filtros_estado: radar.filtros.estado ?? "",
        notif_canal: radar.notif_canal,
        notif_score_minimo: radar.notif_score_minimo,
      })
    } else {
      form.reset({
        nombre: "",
        descripcion: "",
        filtros_q: "",
        filtros_estado: "",
        notif_canal: "email",
        notif_score_minimo: 0,
      })
    }
  }, [radar, open, form])

  const mutation = useMutation({
    mutationFn: (values: RadarFormValues) => {
      const payload = {
        nombre: values.nombre,
        ...(values.descripcion ? { descripcion: values.descripcion } : {}),
        filtros: {
          ...(values.filtros_q ? { q: values.filtros_q } : {}),
          ...(values.filtros_estado ? { estado: values.filtros_estado } : {}),
        },
        notif_canal: values.notif_canal,
        notif_score_minimo: values.notif_score_minimo,
      }
      if (esEdicion && radar) {
        return updateRadar(radar.id, payload)
      }
      return createRadar(payload)
    },
    onSuccess: () => {
      toast.success(esEdicion ? "Radar actualizado" : "Radar creado")
      void queryClient.invalidateQueries({ queryKey: ["radares"] })
      onOpenChange(false)
    },
    onError: (err: Error) => {
      toast.error(`Error: ${err.message}`)
    },
  })

  const onSubmit = (values: RadarFormValues) => {
    mutation.mutate(values)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{esEdicion ? "Editar radar" : "Nuevo radar"}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            {/* Nombre */}
            <FormField
              control={form.control}
              name="nombre"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre</FormLabel>
                  <FormControl>
                    <Input placeholder="Ej: Construcción región Metropolitana" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Descripción */}
            <FormField
              control={form.control}
              name="descripcion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Descripción (opcional)</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Descripción del radar..."
                      rows={2}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {/* Filtros */}
            <div className="rounded-md border p-3 space-y-3">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Filtros de búsqueda
              </p>
              <FormField
                control={form.control}
                name="filtros_q"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Palabras clave</FormLabel>
                    <FormControl>
                      <Input placeholder="Ej: consultoría, tecnología..." {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="filtros_estado"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Estado</FormLabel>
                    <Select
                      value={field.value ?? ""}
                      onValueChange={field.onChange}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Todos los estados" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        <SelectItem value="">Todos los estados</SelectItem>
                        {ESTADOS_LICITACION.map((e) => (
                          <SelectItem key={e.value} value={e.value}>
                            {e.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            {/* Notificaciones */}
            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="notif_canal"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Canal de notificación</FormLabel>
                    <Select value={field.value} onValueChange={field.onChange}>
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {NOTIF_CANAL_OPCIONES.map((o) => (
                          <SelectItem key={o.value} value={o.value}>
                            {o.label}
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
                name="notif_score_minimo"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Score mínimo (0-100)</FormLabel>
                    <FormControl>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        {...field}
                        onChange={(e) => field.onChange(Number(e.target.value))}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending
                  ? "Guardando..."
                  : esEdicion
                    ? "Guardar cambios"
                    : "Crear radar"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
