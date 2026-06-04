import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { getMe, ApiError } from "@/lib/api"
import { Sidebar } from "@/components/layout/sidebar"

/**
 * Layout protegido del dashboard.
 *
 * El middleware (src/middleware.ts) garantiza que:
 * - Si no hay access_token válido y el refresh falla → redirect a /login (antes de llegar aquí)
 * - Si el access_token expiró pero había refresh_token → el middleware ya renovó la cookie
 *
 * Por eso este layout puede asumir que el access_token es válido y hacer
 * solo un fetch a /auth/me sin lógica de refresh duplicada.
 *
 * Redirects adicionales que maneja este layout:
 * - must_change_password=true → redirect a /change-password
 * - onboarding no completado → redirect a /onboarding
 *
 * onboarding_completado viene incluido en /auth/me (EmpresaBasica),
 * eliminando la necesidad de una segunda llamada a /empresa/me.
 */
export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value

  if (!accessToken) {
    redirect("/login")
  }

  let user
  try {
    user = await getMe(accessToken)
  } catch (error) {
    // 401 aquí significa que el token que llegó del middleware ya no es válido
    // en el backend (revocado, o desfase de tiempo). Redirigir a login.
    if (error instanceof ApiError && error.status === 401) {
      redirect("/login")
    }
    redirect("/login")
  }

  if (user.must_change_password) {
    redirect("/change-password")
  }

  if (!user.empresa?.onboarding_completado) {
    redirect("/onboarding")
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar user={user} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <main className="flex-1 overflow-y-auto bg-muted/20 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
