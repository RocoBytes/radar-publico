import { redirect } from "next/navigation"

/** Redirige la raíz al dashboard (que tiene su propia protección de sesión). */
export default function RootPage() {
  redirect("/dashboard")
}
