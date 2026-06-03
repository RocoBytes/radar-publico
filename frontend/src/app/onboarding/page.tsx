import { cookies } from "next/headers"
import { redirect } from "next/navigation"
import { getMe, ApiError } from "@/lib/api"
import { OnboardingWizard } from "./_components/onboarding-wizard"

/**
 * Página de onboarding.
 * - Sin token → redirect /login
 * - Onboarding ya completado → redirect /dashboard
 * - Todo ok → renderiza el wizard
 *
 * onboarding_completado viene incluido en /auth/me sin costo extra de DB.
 */
export default async function OnboardingPage() {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get("access_token")?.value

  if (!accessToken) {
    redirect("/login")
  }

  try {
    const user = await getMe(accessToken)
    if (user.empresa?.onboarding_completado) {
      redirect("/dashboard")
    }
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      redirect("/login")
    }
    // Otros errores: dejar pasar al wizard (empresa aún no existe)
  }

  return <OnboardingWizard />
}
