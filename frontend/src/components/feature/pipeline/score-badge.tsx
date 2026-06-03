"use client"

import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { ScoreBreakdown } from "./score-breakdown"
import type { ScoreJustificacion } from "@/types/pipeline"

interface ScoreBadgeProps {
  score: number | null
  justificacion: ScoreJustificacion | null
}

export function ScoreBadge({ score, justificacion }: ScoreBadgeProps) {
  const [open, setOpen] = useState(false)

  const tieneContenido = score !== null || justificacion !== null

  const claseColor =
    score !== null && score >= 70
      ? "bg-green-100 text-green-800 border-green-300"
      : score !== null && score >= 40
        ? "bg-yellow-100 text-yellow-800 border-yellow-300"
        : "bg-slate-100 text-slate-600 border-slate-200"

  const claseBase =
    "inline-flex items-center rounded-full border px-3 py-1 text-sm font-bold"

  if (!tieneContenido) {
    return (
      <span className={`${claseBase} bg-slate-100 text-slate-600 border-slate-200`}>
        —
      </span>
    )
  }

  return (
    <>
      <button
        type="button"
        className={`${claseBase} ${claseColor} cursor-pointer`}
        aria-label={`Score: ${score ?? "pendiente"}. Click para ver desglose`}
        onClick={() => setOpen(true)}
      >
        Score: {score ?? "—"}
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Desglose del Score</DialogTitle>
          </DialogHeader>
          <ScoreBreakdown justificacion={justificacion} />
        </DialogContent>
      </Dialog>
    </>
  )
}
