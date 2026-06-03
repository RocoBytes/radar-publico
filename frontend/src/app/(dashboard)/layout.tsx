import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { getMe, ApiError } from "@/lib/api"
import { Sidebar } from "@/components/layout/sidebar"

/**
 * Layout protegido del dashboard.
 * - Sin sesión válida → redirect a /login (middleware lo intercepta primero)
 * - Con must_change_password=true → redirect a /change-password
 * - Sin onboarding completado → redirect a /onboarding
 *
 * onboarding_completado viene incluido en /auth/me (EmpresaBasica),
 * eliminando la segunda llamada a /empresa/me que existía antes.
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
    if (error instanceof ApiError && error.status === 401) {
      const internalApi =
        process.env["INTERNAL_API_URL"] ?? "http://localhost:8000"
      const refreshToken = cookieStore.get("refresh_token")?.value

      if (!refreshToken) {
        redirect("/login")
      }

      const refreshResponse = await fetch(`${internalApi}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      }).catch(() => null)

      if (!refreshResponse?.ok) {
        redirect("/login")
      }

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
