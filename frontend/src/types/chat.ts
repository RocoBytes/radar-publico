export type MensajeRol = "user" | "assistant" | "system"

export interface Cita {
  chunk_id: string
  pagina: number | null
  fragmento: string
}

export interface ChatMensaje {
  id: string
  rol: MensajeRol
  contenido: string
  citas: Cita[]
  modelo_usado: string | null
  tokens_input: number | null
  tokens_output: number | null
  created_at: string
}

export interface Conversacion {
  id: string
  licitacion_codigo: string | null
  mensajes: ChatMensaje[]
}

/** Eventos SSE discriminados por tipo */
export type SseEvent =
  | { tipo: "delta"; texto: string }
  | { tipo: "citas"; citas: Cita[] }
  | { tipo: "fin"; mensaje_id: string }
  | { tipo: "error"; detail: string }
