"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
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

/** Schema de validación del formulario de login */
const loginSchema = z.object({
  email: z
    .string()
    .min(1, "El email es obligatorio")
    .email("Ingresá un email válido"),
  password: z.string().min(1, "La contraseña es obligatoria"),
})

type LoginFormValues = z.infer<typeof loginSchema>

/** Respuesta exitosa del Route Handler de login */
interface LoginRouteResponse {
  must_change_password: boolean
}

export function LoginForm() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  })

  const isLoading = form.formState.isSubmitting

  async function onSubmit(values: LoginFormValues) {
    setServerError(null)

    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(values),
    })

    if (!response.ok) {
      if (response.status === 429) {
        setServerError("Demasiados intentos. Esperá unos minutos e intentá de nuevo.")
        return
      }
      // Mensaje genérico para 401 (regla de oro #4: nunca distinguir email vs password)
      setServerError("Credenciales inválidas")
      return
    }

    const data = (await response.json()) as LoginRouteResponse

    if (data.must_change_password) {
      router.push("/change-password")
    } else {
      router.push("/dashboard")
    }
  }

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
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

          <FormField
            control={form.control}
            name="password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Contraseña</FormLabel>
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

          {serverError !== null && (
            <p role="alert" className="text-sm font-medium text-destructive">
              {serverError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Ingresando…" : "Ingresar"}
          </Button>
        </form>
      </Form>
    </div>
  )
}
