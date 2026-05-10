import type { Metadata } from "next"
import { ChangePasswordForm } from "./_components/change-password-form"

export const metadata: Metadata = {
  title: "Cambiar contraseña — Radar Público",
}

export default function ChangePasswordPage() {
  return (
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Cambiar contraseña</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Ingresá tu contraseña actual y definí una nueva.
          </p>
        </div>
        <ChangePasswordForm />
      </div>
    </main>
  )
}
