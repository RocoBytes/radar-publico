import type { Metadata } from "next"
import { LoginForm } from "./_components/login-form"

export const metadata: Metadata = {
  title: "Iniciar sesión — Radar Público",
}

export default function LoginPage() {
  return (
    <>
      <div className="mb-6 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Iniciá sesión</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ingresá con tu cuenta para continuar
        </p>
      </div>
      <LoginForm />
    </>
  )
}
