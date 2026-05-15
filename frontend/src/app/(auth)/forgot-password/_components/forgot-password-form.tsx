"use client"

import { useState } from "react"
import Link from "next/link"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
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

/** Schema de validación del formulario de recuperación de contraseña */
const forgotPasswordSchema = z.object({
  email: z.string().email("Email inválido"),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

export function ForgotPasswordForm() {
  const [submitted, setSubmitted] = useState(false)
  const [networkError, setNetworkError] = useState<string | null>(null)

  const form = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  })

  const isLoading = form.formState.isSubmitting

  async function onSubmit(values: ForgotPasswordFormValues) {
    setNetworkError(null)

    try {
      await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      })
      // Siempre mostramos éxito para no revelar si el email existe (anti-enumeración)
      setSubmitted(true)
    } catch {
      setNetworkError("Error de conexión, intentá de nuevo.")
    }
  }

  if (submitted) {
    return (
      <div className="rounded-lg border bg-white p-6 shadow-sm space-y-4 text-center">
        <p className="text-sm text-muted-foreground">
          Si el email está registrado, recibirás un link en los próximos minutos.
        </p>
        <Link
          href="/login"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Volver al login
        </Link>
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4">
        <p className="text-sm text-muted-foreground">
          Ingresá tu email y te enviamos un link.
        </p>
      </div>
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            control={form.control}
            name="email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Email</FormLabel>
                <FormControl>
                  <Input
                    type="email"
                    placeholder="usuario@empresa.cl"
                    autoComplete="email"
                    disabled={isLoading}
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          {networkError !== null && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {networkError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Enviando..." : "Enviar link"}
          </Button>

          <div className="text-center">
            <Link
              href="/login"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ← Volver al login
            </Link>
          </div>
        </form>
      </Form>
    </div>
  )
}
