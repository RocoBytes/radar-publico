"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"

/** Regex de política de contraseña: mínimo 10 chars, mayúscula, minúscula, dígito */
const PASSWORD_POLICY = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,}$/

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "La contraseña actual es obligatoria"),
    new_password: z
      .string()
      .regex(
        PASSWORD_POLICY,
        "La contraseña debe tener al menos 10 caracteres, una mayúscula, una minúscula y un número."
      ),
    confirm_password: z.string().min(1, "Confirmá la contraseña nueva"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Las contraseñas nuevas no coinciden",
    path: ["confirm_password"],
  })

type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

interface ErrorResponse {
  detail: string
}

export function ChangePasswordForm() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)

  const form = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  })

  const isLoading = form.formState.isSubmitting

  async function onSubmit(values: ChangePasswordFormValues) {
    setServerError(null)

    const response = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: values.current_password,
        new_password: values.new_password,
      }),
    })

    if (!response.ok) {
      if (response.status === 401) {
        setServerError("La contraseña actual es incorrecta.")
        return
      }
      const body = (await response.json().catch(() => ({
        detail: "Error al cambiar la contraseña",
      }))) as ErrorResponse
      setServerError(body.detail)
      return
    }

    toast.success("Contraseña actualizada correctamente")
    router.push("/dashboard")
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            control={form.control}
            name="current_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Contraseña actual</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    placeholder="••••••••••"
                    autoComplete="current-password"
                    disabled={isLoading}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Contraseña nueva</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    placeholder="••••••••••"
                    autoComplete="new-password"
                    disabled={isLoading}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="confirm_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Confirmar contraseña nueva</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    placeholder="••••••••••"
                    autoComplete="new-password"
                    disabled={isLoading}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {serverError !== null && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {serverError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Guardando…" : "Cambiar contraseña"}
          </Button>
        </form>
      </Form>
    </div>
  )
}
