import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { getMe } from "@/lib/api"
import { ApiError } from "@/lib/api"

/**
 * Layout protegido del dashboard.
 * - Sin sesión válida → redirect a /login
 * - Con must_change_password=true → redirect a /change-password
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
      // Token expirado: intentar refresh server-side
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

      // Tras refresh exitoso en SSR, redirigir para que el Route Handler rote las cookies
      // La solución limpia: redirigir a un endpoint que haga el refresh y devuelva a la ruta actual
      redirect("/login")
    }
    redirect("/login")
  }

  if (user.must_change_password) {
    redirect("/change-password")
  }

  return <>{children}</>
}
