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
    <main className="flex min-h-svh items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Radar Público</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Nueva contraseña
          </p>
        </div>
        <ResetPasswordForm token={token} />
      </div>
    </main>
  )
}
