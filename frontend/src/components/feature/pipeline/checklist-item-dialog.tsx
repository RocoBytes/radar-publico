"use client"

import { useEffect } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import type { ChecklistItem, ChecklistItemCreateRequest } from "@/types/checklist"

const formSchema = z.object({
  nombre: z.string().min(1, "Requerido").max(255, "Máximo 255 caracteres"),
  descripcion: z.string().max(2000, "Máximo 2000 caracteres"),
  obligatorio: z.boolean(),
})

type FormValues = z.infer<typeof formSchema>

interface ChecklistItemDialogProps {
  open: boolean
  onClose: () => void
  onSave: (data: ChecklistItemCreateRequest) => void
  item?: ChecklistItem
  isPending?: boolean
}

export function ChecklistItemDialog({
  open,
  onClose,
  onSave,
  item,
  isPending,
}: ChecklistItemDialogProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: { nombre: "", descripcion: "", obligatorio: false },
  })

  useEffect(() => {
    if (open) {
      form.reset({
        nombre: item?.nombre ?? "",
        descripcion: item?.descripcion ?? "",
        obligatorio: item?.obligatorio ?? false,
      })
    }
  }, [open, item, form])

  function handleSubmit(values: FormValues) {
    onSave({
      nombre: values.nombre,
      descripcion: values.descripcion || undefined,
      obligatorio: values.obligatorio,
    })
  }

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{item ? "Editar ítem" : "Nuevo ítem"}</DialogTitle>
        </DialogHeader>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="nombre"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nombre</FormLabel>
                  <FormControl>
                    <Input
                      placeholder="Ej: Certificado de deuda tributaria"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="descripcion"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>
                    Descripción{" "}
                    <span className="text-muted-foreground font-normal">
                      (opcional)
                    </span>
                  </FormLabel>
                  <FormControl>
                    <Textarea rows={3} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="obligatorio"
              render={({ field }) => (
                <FormItem className="flex items-center justify-between rounded-md border px-4 py-3">
                  <FormLabel className="font-normal cursor-pointer">
                    Documento obligatorio
                  </FormLabel>
                  <FormControl>
                    <Switch
                      checked={field.value}
                      onCheckedChange={field.onChange}
                    />
                  </FormControl>
                </FormItem>
              )}
            />
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                disabled={isPending}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={isPending}>
                {isPending ? "Guardando..." : "Guardar"}
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  )
}
