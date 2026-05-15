import type { Metadata } from "next"
import { ForgotPasswordForm } from "./_components/forgot-password-form"

export const metadata: Metadata = {
  title: "Recuperar contraseña — Radar Público",
}

export default function ForgotPasswordPage() {
  return (
    <>
      <div className="mb-6 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Recuperar contraseña</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Te enviamos un link para restablecer tu contraseña.
        </p>
      </div>
      <ForgotPasswordForm />
    </>
  )
}
