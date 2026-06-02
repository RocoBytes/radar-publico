"use client"

import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { submitTicketRequest } from "@/lib/api"

interface Props {
  onNext: () => void
}

/**
 * Paso 2 del onboarding: solicitud del ticket de integración ChileCompra.
 * El usuario puede enviar su ticket o saltear este paso.
 */
export function StepTicket({ onNext }: Props) {
  const [ticketTexto, setTicketTexto] = useState("")
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleEnviar() {
    if (!ticketTexto.trim()) {
      setError("Ingresá tu ticket antes de enviar.")
      return
    }
    setError(null)
    setEnviando(true)
    try {
      await submitTicketRequest(ticketTexto.trim())
      toast.success("Solicitud enviada. El equipo activará tu cuenta pronto.")
      onNext()
    } catch {
      setError("No se pudo enviar la solicitud. Intentá de nuevo.")
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Ticket de integración ChileCompra</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          El ticket es una credencial que ChileCompra asigna a tu empresa.
          Lo necesitamos para consultar licitaciones en tu nombre.
        </p>
      </div>

      {/* Instrucciones paso a paso */}
      <div className="rounded-lg bg-muted/50 p-4">
        <p className="mb-3 text-sm font-medium">
          Cómo obtener tu ticket de integración:
        </p>
        <ol className="space-y-2 text-sm text-muted-foreground">
          <li className="flex gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              1
            </span>
            <span>
              Ingresá a{" "}
              <a
                href="https://api.mercadopublico.cl"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-primary underline-offset-4 hover:underline"
              >
                api.mercadopublico.cl
              </a>
            </span>
          </li>
          <li className="flex gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              2
            </span>
            <span>
              Iniciá sesión con tu RUT y contraseña de Mercado Público
            </span>
          </li>
          <li className="flex gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              3
            </span>
            <span>
              En tu perfil encontrarás tu{" "}
              <strong>Ticket de Integración</strong> — es un código como{" "}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
                XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
              </code>
            </span>
          </li>
          <li className="flex gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              4
            </span>
            <span>Copialo y pegalo aquí abajo</span>
          </li>
        </ol>
      </div>

      {/* Campo del ticket */}
      <div className="space-y-1.5">
        <Label htmlFor="ticket_texto">Tu ticket de integración</Label>
        <Input
          id="ticket_texto"
          value={ticketTexto}
          onChange={(e) => {
            setTicketTexto(e.target.value)
            if (error) setError(null)
          }}
          placeholder="XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
          disabled={enviando}
          className="font-mono"
        />
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>

      {/* Acciones */}
      <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
        <Button
          type="button"
          variant="outline"
          onClick={onNext}
          disabled={enviando}
        >
          Continuar sin ticket por ahora
        </Button>
        <Button type="button" onClick={handleEnviar} disabled={enviando}>
          {enviando ? "Enviando…" : "Enviar al equipo de soporte"}
        </Button>
      </div>
    </div>
  )
}
