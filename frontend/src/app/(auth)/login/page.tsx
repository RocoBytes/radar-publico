import type { Metadata } from "next"
import { LoginForm } from "./_components/login-form"

export const metadata: Metadata = {
  title: "Iniciar sesión — Radar Público",
}

export default function LoginPage() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Radar Público</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Ingresá con tu cuenta para continuar
          </p>
        </div>
        <LoginForm />
      </div>
    </main>
  )
}
