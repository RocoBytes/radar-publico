import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { getMe } from "@/lib/api"
import { ApiError } from "@/lib/api"
import { LogoutButton } from "./_components/logout-button"

export default async function DashboardPage() {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value

  if (!accessToken) {
    redirect("/login")
  }

  let user
  try {
    user = await getMe(accessToken)
  } catch (error) {
    if (error instanceof ApiError) {
      redirect("/login")
    }
    redirect("/login")
  }

  const empresaNombre = user.empresa?.razon_social ?? user.email

  return (
    <main className="flex min-h-svh flex-col">
      <header className="border-b bg-white px-6 py-4">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <span className="text-lg font-semibold">Radar Público</span>
          <LogoutButton />
        </div>
      </header>

      <section className="mx-auto w-full max-w-4xl flex-1 px-6 py-12">
        <h1 className="text-3xl font-bold">
          Hola, {empresaNombre} 👋
        </h1>
        <p className="mt-2 text-muted-foreground">
          Tu dashboard está en construcción. Volvé en el Sprint 2.
        </p>

        <div className="mt-8 rounded-lg border bg-muted/20 p-6">
          <p className="text-sm text-muted-foreground">
            Sesión activa como <strong>{user.email}</strong>
          </p>
        </div>
      </section>
    </main>
  )
}
