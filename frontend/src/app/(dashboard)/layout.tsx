import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { Sidebar } from "@/components/layout/sidebar"
import { AuthGuard } from "./_components/auth-guard"

/**
 * Layout protegido del dashboard.
 *
 * Solo verifica que haya un access_token en cookies.
 * El middleware ya garantiza que el token es válido (o lo renueva).
 * Los checks de must_change_password y onboarding_completado se delegan
 * a AuthGuard (client-side) para no bloquear el RSC en cada navegación.
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

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <AuthGuard />
        <main className="flex-1 overflow-y-auto bg-muted/20 p-6">
          {children}
        </main>
      </div>
    </div>
  )
}
