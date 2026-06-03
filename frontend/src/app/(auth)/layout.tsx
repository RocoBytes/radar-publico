export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="relative flex min-h-svh items-center justify-center overflow-hidden p-4"
      style={{
        background:
          "radial-gradient(ellipse at 30% 20%, hsl(226 71% 40% / 0.07) 0%, transparent 55%), radial-gradient(ellipse at 75% 80%, hsl(226 71% 40% / 0.04) 0%, transparent 50%), hsl(210 38% 98%)",
      }}
    >
      <div className="relative w-full max-w-sm">
        {/* Brand mark */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-lg shadow-primary/20">
            <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6" aria-hidden="true">
              <circle cx="5" cy="19" r="2.5" fill="currentColor" />
              <path d="M5 13a6 6 0 0 1 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              <path d="M5 7a12 12 0 0 1 12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </div>
          <span className="text-lg font-bold tracking-tight">Radar Público</span>
        </div>

        {children}
      </div>
    </div>
  )
}
