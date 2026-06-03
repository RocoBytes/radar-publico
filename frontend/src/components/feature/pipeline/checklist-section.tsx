"use client"

import { useState } from "react"
import { Plus, Sparkles } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import {
  getChecklist,
  createChecklistItem,
  updateChecklistItem,
  deleteChecklistItem,
  bootstrapChecklist,
} from "@/lib/api"
import type {
  ChecklistItem,
  ChecklistItemCreateRequest,
  ChecklistItemUpdateRequest,
} from "@/types/checklist"
import { ChecklistItemRow } from "./checklist-item-row"
import { ChecklistItemDialog } from "./checklist-item-dialog"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

interface ChecklistSectionProps {
  pipelineItemId: string
}

export function ChecklistSection({ pipelineItemId }: ChecklistSectionProps) {
  const queryClient = useQueryClient()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingItem, setEditingItem] = useState<ChecklistItem | undefined>()

  const queryKey = ["pipeline-checklist", pipelineItemId]

  const { data: items = [], isLoading } = useQuery({
    queryKey,
    queryFn: () => getChecklist(pipelineItemId),
  })

  const invalidar = () =>
    void queryClient.invalidateQueries({ queryKey })

  const crearMutation = useMutation({
    mutationFn: (data: ChecklistItemCreateRequest) =>
      createChecklistItem(pipelineItemId, data),
    onSuccess: () => {
      toast.success("Ítem creado")
      handleDialogClose()
      invalidar()
    },
    onError: (err: Error) => toast.error(`Error: ${err.message}`),
  })

  const actualizarMutation = useMutation({
    mutationFn: ({
      itemId,
      data,
    }: {
      itemId: string
      data: ChecklistItemUpdateRequest
    }) => updateChecklistItem(pipelineItemId, itemId, data),
    onSuccess: () => {
      toast.success("Ítem actualizado")
      handleDialogClose()
      invalidar()
    },
    onError: (err: Error) => toast.error(`Error: ${err.message}`),
  })

  const eliminarMutation = useMutation({
    mutationFn: (itemId: string) => deleteChecklistItem(pipelineItemId, itemId),
    onSuccess: () => {
      toast.success("Ítem eliminado")
      invalidar()
    },
    onError: (err: Error) => toast.error(`Error: ${err.message}`),
  })

  const bootstrapMutation = useMutation({
    mutationFn: () => bootstrapChecklist(pipelineItemId),
    onSuccess: (res) => {
      if (res.creados === 0) {
        toast.info("No hay documentos del análisis para importar")
      } else {
        toast.success(
          `${res.creados} ítem${res.creados !== 1 ? "s" : ""} importado${res.creados !== 1 ? "s" : ""} desde el análisis IA`
        )
      }
      invalidar()
    },
    onError: (err: Error) => toast.error(`Error: ${err.message}`),
  })

  function handleToggle(item: ChecklistItem) {
    const estado = item.estado === "completado" ? "pendiente" : "completado"
    actualizarMutation.mutate({ itemId: item.id, data: { estado } })
  }

  function handleEdit(item: ChecklistItem) {
    setEditingItem(item)
    setDialogOpen(true)
  }

  function handleSave(data: ChecklistItemCreateRequest) {
    if (editingItem) {
      actualizarMutation.mutate({ itemId: editingItem.id, data })
    } else {
      crearMutation.mutate(data)
    }
  }

  function handleDialogClose() {
    setDialogOpen(false)
    setEditingItem(undefined)
  }

  const completadoCount = items.filter((i) => i.estado === "completado").length

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-medium">Checklist documental</h2>
          {items.length > 0 && (
            <p className="text-xs text-muted-foreground">
              {completadoCount}/{items.length} completado
              {items.length !== 1 ? "s" : ""}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => bootstrapMutation.mutate()}
            disabled={bootstrapMutation.isPending}
          >
            <Sparkles className="h-3.5 w-3.5 mr-1.5" />
            Importar desde IA
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setEditingItem(undefined)
              setDialogOpen(true)
            }}
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            Agregar
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Sin ítems. Agregá uno manualmente o importá desde el análisis IA.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <ChecklistItemRow
              key={item.id}
              item={item}
              onToggle={handleToggle}
              onEdit={handleEdit}
              onDelete={(id) => eliminarMutation.mutate(id)}
              isUpdating={
                actualizarMutation.isPending &&
                actualizarMutation.variables?.itemId === item.id
              }
              isDeleting={
                eliminarMutation.isPending &&
                eliminarMutation.variables === item.id
              }
            />
          ))}
        </div>
      )}

      <ChecklistItemDialog
        open={dialogOpen}
        onClose={handleDialogClose}
        onSave={handleSave}
        item={editingItem}
        isPending={crearMutation.isPending || actualizarMutation.isPending}
      />
    </div>
  )
}
