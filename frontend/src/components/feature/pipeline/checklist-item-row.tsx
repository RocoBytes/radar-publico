"use client"

import { CheckCircle2, Circle, Pencil, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import type { ChecklistItem } from "@/types/checklist"

interface ChecklistItemRowProps {
  item: ChecklistItem
  onToggle: (item: ChecklistItem) => void
  onEdit: (item: ChecklistItem) => void
  onDelete: (itemId: string) => void
  isUpdating?: boolean
  isDeleting?: boolean
}

export function ChecklistItemRow({
  item,
  onToggle,
  onEdit,
  onDelete,
  isUpdating,
  isDeleting,
}: ChecklistItemRowProps) {
  const completado = item.estado === "completado"

  return (
    <div className="flex items-start gap-3 rounded-md border px-4 py-3 hover:bg-muted/30 transition-colors">
      <button
        type="button"
        onClick={() => onToggle(item)}
        disabled={isUpdating}
        className="mt-0.5 shrink-0 text-muted-foreground hover:text-primary transition-colors disabled:opacity-50"
        aria-label={completado ? "Marcar como pendiente" : "Marcar como completado"}
      >
        {completado ? (
          <CheckCircle2 className="h-4 w-4 text-green-600" />
        ) : (
          <Circle className="h-4 w-4" />
        )}
      </button>

      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`text-sm font-medium ${completado ? "line-through text-muted-foreground" : ""}`}
          >
            {item.nombre}
          </span>
          {item.obligatorio && (
            <Badge
              variant="outline"
              className="text-xs px-1.5 py-0 h-4 border-orange-300 text-orange-700"
            >
              Obligatorio
            </Badge>
          )}
          {item.origen === "ia_generado" && (
            <Badge
              variant="outline"
              className="text-xs px-1.5 py-0 h-4 border-blue-300 text-blue-700"
            >
              IA
            </Badge>
          )}
        </div>
        {item.descripcion && (
          <p className="text-xs text-muted-foreground">{item.descripcion}</p>
        )}
      </div>

      <div className="flex items-center gap-1 shrink-0">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-muted-foreground hover:text-foreground"
          onClick={() => onEdit(item)}
        >
          <Pencil className="h-3.5 w-3.5" />
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-destructive"
              disabled={isDeleting}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>¿Eliminar ítem?</AlertDialogTitle>
              <AlertDialogDescription>
                Esta acción no se puede deshacer.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancelar</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => onDelete(item.id)}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                Eliminar
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  )
}
