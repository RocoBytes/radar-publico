"use client"

import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Bot, Send } from "lucide-react"
import { getChatHistorial, streamChatMensaje } from "@/lib/api"
import type { ChatMensaje, Cita } from "@/types/chat"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Textarea } from "@/components/ui/textarea"

const PREGUNTAS_SUGERIDAS = [
  "¿Pide boleta de garantía?",
  "¿Cuál es la experiencia mínima requerida?",
  "¿Cómo se evalúa el precio?",
]

/** Burbuja de una cita de las bases (chunk referenciado) */
function CitaBurbuja({ cita }: { cita: Cita }) {
  return (
    <div className="text-xs text-muted-foreground bg-muted/50 rounded px-2 py-1">
      {cita.pagina !== null && (
        <span className="font-medium">Pág. {cita.pagina} — </span>
      )}
      {cita.fragmento.length > 120
        ? cita.fragmento.slice(0, 120) + "..."
        : cita.fragmento}
    </div>
  )
}

/** Burbuja de un mensaje del chat (user o assistant) */
function MensajeBurbuja({
  mensaje,
}: {
  mensaje: ChatMensaje
}) {
  const esUsuario = mensaje.rol === "user"

  return (
    <div className={`flex ${esUsuario ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-lg px-4 py-2.5 text-sm ${
          esUsuario
            ? "bg-slate-100 text-slate-900 dark:bg-slate-700 dark:text-slate-100"
            : "bg-white border border-border text-foreground dark:bg-card"
        }`}
      >
        <p className="whitespace-pre-wrap break-words">{mensaje.contenido}</p>
        {!esUsuario && mensaje.citas.length > 0 && (
          <div className="mt-2 space-y-1">
            {mensaje.citas.map((c) => (
              <CitaBurbuja key={c.chunk_id} cita={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Burbuja del mensaje assistant mientras se genera (streaming) */
function MensajeStreaming({
  texto,
  citas,
}: {
  texto: string
  citas: Cita[]
}) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-lg px-4 py-2.5 text-sm bg-white border border-border text-foreground dark:bg-card">
        <p className="whitespace-pre-wrap break-words">
          {texto}
          <span className="inline-block w-0.5 h-4 ml-0.5 bg-foreground animate-pulse align-text-bottom" />
        </p>
        {citas.length > 0 && (
          <div className="mt-2 space-y-1">
            {citas.map((c) => (
              <CitaBurbuja key={c.chunk_id} cita={c} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface ChatPanelProps {
  codigo: string
}

export function ChatPanel({ codigo }: ChatPanelProps) {
  const [mensajes, setMensajes] = useState<ChatMensaje[]>([])
  const [streamingText, setStreamingText] = useState("")
  const [pendingCitas, setPendingCitas] = useState<Cita[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [rateLimitAlcanzado, setRateLimitAlcanzado] = useState(false)
  const [errorMensaje, setErrorMensaje] = useState<string | null>(null)
  const [input, setInput] = useState("")
  const scrollRef = useRef<HTMLDivElement>(null)

  // Carga historial inicial (TanStack Query v5: onSuccess fue removido, usar useEffect)
  const { data: historialData, isLoading } = useQuery({
    queryKey: ["chat", codigo],
    queryFn: () => getChatHistorial(codigo),
  })

  useEffect(() => {
    if (historialData) {
      setMensajes(historialData.mensajes.filter((m) => m.rol !== "system"))
    }
  }, [historialData])

  // Auto-scroll al llegar nuevos mensajes o durante streaming
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [mensajes, streamingText])

  const handleSubmit = async (contenido: string) => {
    const texto = contenido.trim()
    if (!texto || isStreaming) return

    setErrorMensaje(null)
    setRateLimitAlcanzado(false)

    // Mensaje optimista del usuario
    const mensajeUsuario: ChatMensaje = {
      id: `optimistic-${Date.now()}`,
      rol: "user",
      contenido: texto,
      citas: [],
      modelo_usado: null,
      tokens_input: null,
      tokens_output: null,
      created_at: new Date().toISOString(),
    }
    setMensajes((prev) => [...prev, mensajeUsuario])
    setInput("")
    setIsStreaming(true)
    setStreamingText("")
    setPendingCitas([])

    let textoAcumulado = ""
    let citasFinales: Cita[] = []
    let mensajeIdFinal = ""

    try {
      await streamChatMensaje(
        codigo,
        texto,
        // onDelta
        (fragmento) => {
          textoAcumulado += fragmento
          setStreamingText(textoAcumulado)
        },
        // onCitas
        (citas) => {
          citasFinales = citas
          setPendingCitas(citas)
        },
        // onFin
        (mensajeId) => {
          mensajeIdFinal = mensajeId
        },
        // onError
        (detail) => {
          const esRateLimit =
            detail.toLowerCase().includes("rate limit") ||
            detail.toLowerCase().includes("límite") ||
            detail.toLowerCase().includes("100")
          if (esRateLimit) {
            setRateLimitAlcanzado(true)
          } else {
            setErrorMensaje(detail)
          }
        }
      )
    } finally {
      // Si hubo texto generado, materializar el mensaje assistant
      if (textoAcumulado) {
        const mensajeAssistant: ChatMensaje = {
          id: mensajeIdFinal || `assistant-${Date.now()}`,
          rol: "assistant",
          contenido: textoAcumulado,
          citas: citasFinales,
          modelo_usado: null,
          tokens_input: null,
          tokens_output: null,
          created_at: new Date().toISOString(),
        }
        setMensajes((prev) => [...prev, mensajeAssistant])
        setStreamingText("")
        setPendingCitas([])
      }
      setIsStreaming(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      void handleSubmit(input)
    }
  }

  return (
    <div className="flex flex-col h-[500px] rounded-lg border border-border overflow-hidden">
      {/* Área de mensajes */}
      <ScrollArea className="flex-1">
        <div className="p-4 space-y-3">
          {/* Estado inicial de carga */}
          {isLoading && (
            <div className="flex justify-center py-8">
              <p className="text-sm text-muted-foreground">Cargando historial...</p>
            </div>
          )}

          {/* Sin mensajes todavía: preguntas sugeridas */}
          {!isLoading && mensajes.length === 0 && !isStreaming && (
            <div className="space-y-4 py-4">
              <div className="flex flex-col items-center gap-2 text-center">
                <Bot className="h-10 w-10 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">
                  Asistente IA con conocimiento de las bases de esta licitación
                </p>
              </div>
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground font-medium">
                  Preguntas frecuentes:
                </p>
                {PREGUNTAS_SUGERIDAS.map((pregunta) => (
                  <button
                    key={pregunta}
                    type="button"
                    onClick={() => void handleSubmit(pregunta)}
                    className="block w-full text-left rounded-md border border-border bg-muted/30 px-3 py-2 text-sm hover:bg-muted/60 transition-colors"
                  >
                    {pregunta}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Mensajes del historial */}
          {mensajes.map((m) => (
            <MensajeBurbuja key={m.id} mensaje={m} />
          ))}

          {/* Mensaje en streaming */}
          {isStreaming && (
            <MensajeStreaming texto={streamingText} citas={pendingCitas} />
          )}

          {/* Aviso de rate limit */}
          {rateLimitAlcanzado && (
            <div className="flex justify-center">
              <Badge variant="destructive" className="text-xs">
                Límite diario de mensajes alcanzado (100/día).
              </Badge>
            </div>
          )}

          {/* Error genérico */}
          {errorMensaje && (
            <div className="flex justify-center">
              <p className="text-xs text-destructive">{errorMensaje}</p>
            </div>
          )}

          {/* Ancla para auto-scroll */}
          <div ref={scrollRef} />
        </div>
      </ScrollArea>

      {/* Input */}
      <div className="border-t border-border p-3 space-y-2">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void handleSubmit(input)
          }}
          className="flex gap-2 items-end"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Preguntá sobre las bases técnicas... (Enter para enviar)"
            rows={2}
            className="resize-none flex-1 text-sm"
            disabled={isStreaming || rateLimitAlcanzado}
          />
          <Button
            type="submit"
            size="icon"
            disabled={isStreaming || !input.trim() || rateLimitAlcanzado}
            className="shrink-0"
          >
            <Send className="h-4 w-4" />
            <span className="sr-only">Enviar mensaje</span>
          </Button>
        </form>
        <p className="text-xs text-muted-foreground">
          Shift+Enter para nueva línea · Enter para enviar
        </p>
      </div>
    </div>
  )
}
