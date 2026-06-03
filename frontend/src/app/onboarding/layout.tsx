import type { Metadata } from "next"

export const metadata: Metadata = {
  title: "Configuración inicial — Radar Público",
}

/**
 * Layout del wizard de onboarding.
 * Sin sidebar — centrado, solo logo y contenido del wizard.
 */
export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <div className="min-h-svh bg-muted/20">
      {/* Barra superior con logo */}
      <header className="border-b bg-background px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4" aria-hidden="true">
              <circle cx="5" cy="19" r="2.5" fill="currentColor" />
              <path
                d="M5 13a6 6 0 0 1 6 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M5 7a12 12 0 0 1 12 12"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </div>
          <span className="font-bold tracking-tight">Radar Público</span>
        </div>
      </header>

      {/* Contenido del wizard */}
      <main className="mx-auto max-w-3xl px-6 py-10">{children}</main>
    </div>
  )
}
