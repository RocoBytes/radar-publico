import type { Metadata } from "next"
import { ChangePasswordForm } from "./_components/change-password-form"

export const metadata: Metadata = {
  title: "Cambiar contraseña — Radar Público",
}

export default function ChangePasswordPage() {
  return (
    <>
      <div className="mb-6 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Cambiar contraseña</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Ingresá tu contraseña actual y definí una nueva.
        </p>
      </div>
      <ChangePasswordForm />
    </>
  )
}
