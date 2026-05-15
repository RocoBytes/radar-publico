import type { Metadata } from "next"
import { redirect } from "next/navigation"
import { ResetPasswordForm } from "./_components/reset-password-form"

export const metadata: Metadata = {
  title: "Nueva contraseña — Radar Público",
}

interface ResetPasswordPageProps {
  searchParams: Promise<{ token?: string }>
}

export default async function ResetPasswordPage({
  searchParams,
}: ResetPasswordPageProps) {
  const { token } = await searchParams

  if (!token) {
    redirect("/forgot-password")
  }

  return (
    <>
      <div className="mb-6 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Nueva contraseña</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Definí tu nueva contraseña de acceso.
        </p>
      </div>
      <ResetPasswordForm token={token} />
    </>
  )
}
