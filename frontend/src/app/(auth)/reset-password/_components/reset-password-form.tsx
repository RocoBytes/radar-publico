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

/** Schema de validación del formulario de nueva contraseña */
const resetPasswordSchema = z
  .object({
    new_password: z.string().min(8, "Mínimo 8 caracteres"),
    confirm_password: z.string(),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Las contraseñas no coinciden",
    path: ["confirm_password"],
  })

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

type SubmitState = "idle" | "success" | "expired" | "network-error"

interface ResetPasswordFormProps {
  token: string
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const [submitState, setSubmitState] = useState<SubmitState>("idle")

  const form = useForm<ResetPasswordFormValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  })

  const isLoading = form.formState.isSubmitting

  async function onSubmit(values: ResetPasswordFormValues) {
    setSubmitState("idle")

    let response: Response
    try {
      response = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: values.new_password }),
      })
    } catch {
      setSubmitState("network-error")
      return
    }

    if (response.status === 204) {
      setSubmitState("success")
      return
    }

    if (response.status === 422) {
      setSubmitState("expired")
      return
    }

    // Otros errores inesperados del servidor
    setSubmitState("network-error")
  }

  if (submitState === "success") {
    return (
      <div className="rounded-lg border bg-white p-6 shadow-sm space-y-4 text-center">
        <p className="text-sm text-muted-foreground">
          Contraseña actualizada. Podés iniciar sesión.
        </p>
        <Link
          href="/login"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          Ir al login
        </Link>
      </div>
    )
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <Form {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Nueva contraseña</FormLabel>
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
                <FormLabel>Confirmar contraseña</FormLabel>
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

          {submitState === "expired" && (
            <p role="alert" className="text-sm font-medium text-destructive">
              El link es inválido o expiró.{" "}
              <Link
                href="/forgot-password"
                className="underline hover:no-underline"
              >
                Solicitá uno nuevo
              </Link>
              .
            </p>
          )}

          {submitState === "network-error" && (
            <p role="alert" className="text-sm font-medium text-destructive">
              Error de conexión, intentá de nuevo.
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Cambiando..." : "Cambiar contraseña"}
          </Button>
        </form>
      </Form>
    </div>
  )
}
