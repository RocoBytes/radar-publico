"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Check } from "lucide-react"
import { updateEmpresaMe } from "@/lib/api"
import { StepEmpresa } from "./step-empresa"
import { StepTicket } from "./step-ticket"
import { StepIntereses } from "./step-intereses"
import { StepNotificaciones } from "./step-notificaciones"

const STEPS = [
  "Empresa",
  "Ticket ChileCompra",
  "Mis intereses",
  "Notificaciones",
] as const

type StepIndex = 0 | 1 | 2 | 3

/**
 * Wizard de onboarding con 4 pasos.
 * Gestiona el estado del paso actual y el stepper horizontal.
 * Al completar el paso 4, marca el onboarding como completado y redirige.
 */
export function OnboardingWizard() {
  const router = useRouter()
  const [step, setStep] = useState<StepIndex>(0)
  const [completing, setCompleting] = useState(false)

  function goNext() {
    if (step < 3) {
      setStep((s) => (s + 1) as StepIndex)
    }
  }

  async function handleComplete() {
    setCompleting(true)
    try {
      await updateEmpresaMe({ onboarding_completado: true })
      router.push("/dashboard")
    } catch {
      // Si falla el PATCH, intentar igual la redirección
      router.push("/dashboard")
    }
  }

  return (
    <div className="space-y-8">
      {/* Encabezado */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Configuración inicial
        </h1>
        <p className="mt-1 text-muted-foreground">
          Completá estos pasos para empezar a usar Radar Público.
        </p>
      </div>

      {/* Stepper horizontal */}
      <nav aria-label="Progreso del onboarding">
        <ol className="flex items-center gap-0">
          {STEPS.map((label, index) => {
            const isDone = index < step
            const isCurrent = index === step
            const isLast = index === STEPS.length - 1

            return (
              <li key={label} className="flex flex-1 items-center">
                {/* Paso */}
                <div className="flex flex-col items-center gap-1.5 min-w-0 flex-1">
                  <div
                    className={[
                      "flex h-8 w-8 items-center justify-center rounded-full border-2 text-xs font-semibold transition-colors",
                      isDone
                        ? "border-primary bg-primary text-primary-foreground"
                        : isCurrent
                          ? "border-primary bg-background text-primary"
                          : "border-muted-foreground/30 bg-background text-muted-foreground",
                    ].join(" ")}
                    aria-current={isCurrent ? "step" : undefined}
                  >
                    {isDone ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <span>{index + 1}</span>
                    )}
                  </div>
                  <span
                    className={[
                      "text-xs font-medium text-center leading-tight",
                      isCurrent ? "text-foreground" : "text-muted-foreground",
                    ].join(" ")}
                  >
                    {label}
                  </span>
                </div>

                {/* Conector entre pasos */}
                {!isLast && (
                  <div
                    className={[
                      "h-0.5 flex-1 mx-1 mt-[-20px]",
                      isDone ? "bg-primary" : "bg-muted-foreground/20",
                    ].join(" ")}
                    aria-hidden="true"
                  />
                )}
              </li>
            )
          })}
        </ol>
      </nav>

      {/* Panel del paso activo */}
      <div className="rounded-xl bg-background p-6 shadow-sm ring-1 ring-black/5">
        {step === 0 && <StepEmpresa onNext={goNext} />}
        {step === 1 && <StepTicket onNext={goNext} />}
        {step === 2 && <StepIntereses onNext={goNext} />}
        {step === 3 && (
          <StepNotificaciones
            onComplete={handleComplete}
            completing={completing}
          />
        )}
      </div>
    </div>
  )
}
