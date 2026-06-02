"use client"

import { useState } from "react"
import Link from "next/link"
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

const MAX_ATTEMPTS = 5
const LOCKOUT_MINUTES = 30

function buildErrorMessage(failedAttempts: number, retryAfterSeconds: number | null): string {
  if (retryAfterSeconds !== null) {
    const minutes = Math.ceil(retryAfterSeconds / 60)
    return `Tu cuenta está bloqueada por demasiados intentos fallidos. Podés intentar de nuevo en ${minutes} minuto${minutes !== 1 ? "s" : ""}.`
  }
  const remaining = MAX_ATTEMPTS - failedAttempts
  if (failedAttempts >= MAX_ATTEMPTS) {
    return `Tu cuenta fue bloqueada por ${LOCKOUT_MINUTES} minutos. Usá "¿Olvidaste tu contraseña?" si necesitás acceder antes.`
  }
  if (failedAttempts === MAX_ATTEMPTS - 1) {
    return `Credenciales inválidas. Cuidado: solo te queda 1 intento antes de que tu cuenta se bloquee por ${LOCKOUT_MINUTES} minutos.`
  }
  if (failedAttempts >= 2) {
    return `Credenciales inválidas. Tu cuenta se bloqueará por ${LOCKOUT_MINUTES} minutos si fallás ${remaining} veces más.`
  }
  return "Credenciales inválidas"
}

export function LoginForm() {
  const router = useRouter()
  const [serverError, setServerError] = useState<string | null>(null)
  const [failedAttempts, setFailedAttempts] = useState(0)

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
      const retryAfterRaw = response.headers.get("Retry-After")
      const retryAfter = retryAfterRaw ? parseInt(retryAfterRaw, 10) : null
      const newAttempts = retryAfter !== null ? MAX_ATTEMPTS : failedAttempts + 1
      setFailedAttempts(newAttempts)
      setServerError(buildErrorMessage(newAttempts, retryAfter))
      return
    }

    setFailedAttempts(0)
    const data = (await response.json()) as LoginRouteResponse

    if (data.must_change_password) {
      router.push("/change-password")
    } else {
      router.push("/dashboard")
    }
  }

  return (
    <div className="rounded-xl bg-white p-7 shadow-xl ring-1 ring-black/5">
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
            <p
              role="alert"
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                failedAttempts >= MAX_ATTEMPTS - 1
                  ? "bg-destructive/10 text-destructive"
                  : failedAttempts >= 2
                    ? "bg-amber-50 text-amber-700"
                    : "text-destructive"
              }`}
            >
              {serverError}
            </p>
          )}

          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? "Ingresando…" : "Ingresar"}
          </Button>

          <div className="text-center">
            <Link
              href="/forgot-password"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              ¿Olvidaste tu contraseña?
            </Link>
          </div>
        </form>
      </Form>
    </div>
  )
}
