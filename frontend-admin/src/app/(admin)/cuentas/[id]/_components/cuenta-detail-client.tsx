"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { ChevronLeft, Building2, Key } from "lucide-react";
import { toast } from "sonner";
import { obtenerCuenta, cambiarEstado, cargarTicket, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";
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
} from "@/components/ui/alert-dialog";
import type { UserStatus } from "@/types/admin";

// ─── Subcomponentes ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: UserStatus }) {
  const variants: Record<UserStatus, { label: string; className: string }> = {
    active: {
      label: "Activa",
      className: "bg-green-100 text-green-800 hover:bg-green-100",
    },
    suspended: {
      label: "Suspendida",
      className: "bg-red-100 text-red-800 hover:bg-red-100",
    },
    pending: {
      label: "Pendiente",
      className: "bg-yellow-100 text-yellow-800 hover:bg-yellow-100",
    },
  };

  const variant = variants[status] ?? variants.pending;

  return (
    <Badge className={variant.className} variant="outline">
      {variant.label}
    </Badge>
  );
}

// ─── Schema para el form de ticket ───────────────────────────────────────────

const ticketSchema = z.object({
  ticket: z.string().min(10, "El ticket parece muy corto").max(500, "Ticket inválido"),
});

type TicketFormData = z.infer<typeof ticketSchema>;

// ─── Componente principal ────────────────────────────────────────────────────

type CuentaDetailClientProps = {
  id: string;
};

export function CuentaDetailClient({ id }: CuentaDetailClientProps) {
  const queryClient = useQueryClient();
  const [isChangingStatus, setIsChangingStatus] = useState(false);

  const { data: cuenta, isLoading, isError } = useQuery({
    queryKey: ["cuenta", id],
    queryFn: () => obtenerCuenta(id),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TicketFormData>({
    resolver: zodResolver(ticketSchema),
  });

  async function handleCambiarEstado(accion: "activar" | "suspender") {
    setIsChangingStatus(true);
    try {
      await cambiarEstado(id, accion);
      await queryClient.invalidateQueries({ queryKey: ["cuenta", id] });
      await queryClient.invalidateQueries({ queryKey: ["cuentas"] });
      toast.success(accion === "activar" ? "Cuenta activada" : "Cuenta suspendida");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Error al cambiar estado";
      toast.error(msg);
    } finally {
      setIsChangingStatus(false);
    }
  }

  async function onSubmitTicket(data: TicketFormData) {
    try {
      await cargarTicket(id, data.ticket);
      await queryClient.invalidateQueries({ queryKey: ["cuenta", id] });
      await queryClient.invalidateQueries({ queryKey: ["cuentas"] });
      reset();
      toast.success("Ticket cargado correctamente");
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Error al cargar el ticket";
      toast.error(msg);
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardHeader>
            <Skeleton className="h-6 w-64" />
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isError || !cuenta) {
    return (
      <div className="space-y-4 max-w-2xl">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/cuentas">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Volver a cuentas
          </Link>
        </Button>
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          No se pudo cargar la cuenta.
        </div>
      </div>
    );
  }

  const accionEstado = cuenta.status === "active" ? "suspender" : "activar";
  const labelAccion = accionEstado === "activar" ? "Activar" : "Suspender";
  const descAccion =
    accionEstado === "suspender"
      ? "La cuenta quedará inaccesible para el usuario."
      : "La cuenta volverá a estar activa.";

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Breadcrumb */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/cuentas">
          <ChevronLeft className="h-4 w-4 mr-1" />
          Volver a cuentas
        </Link>
      </Button>

      {/* Header */}
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="space-y-1">
              <CardTitle className="text-lg">{cuenta.email}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">
                  {cuenta.rol}
                </Badge>
                <StatusBadge status={cuenta.status} />
                {cuenta.must_change_password && (
                  <Badge
                    variant="outline"
                    className="text-xs bg-orange-50 text-orange-700 border-orange-200"
                  >
                    Debe cambiar contraseña
                  </Badge>
                )}
              </div>
            </div>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant={accionEstado === "suspender" ? "destructive" : "default"}
                  size="sm"
                  disabled={isChangingStatus || cuenta.status === "pending"}
                >
                  {labelAccion} cuenta
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    ¿{labelAccion} esta cuenta?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {descAccion}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancelar</AlertDialogCancel>
                  <AlertDialogAction
                    onClick={() => void handleCambiarEstado(accionEstado)}
                    className={
                      accionEstado === "suspender"
                        ? "bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        : ""
                    }
                  >
                    Confirmar
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </CardHeader>
        <CardContent>
          <p className="text-xs text-muted-foreground">
            Creada el{" "}
            {format(new Date(cuenta.created_at), "dd 'de' MMMM 'de' yyyy", {
              locale: es,
            })}
          </p>
        </CardContent>
      </Card>

      <Separator />

      {/* Empresa */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Building2 className="h-4 w-4" />
            Empresa
          </CardTitle>
        </CardHeader>
        <CardContent>
          {cuenta.empresa ? (
            <div className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">Razón social</p>
                <p className="text-sm font-medium mt-0.5">
                  {cuenta.empresa.razon_social}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">RUT</p>
                <p className="text-sm font-mono mt-0.5">{cuenta.empresa.rut}</p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">Sin empresa asociada.</p>
          )}
        </CardContent>
      </Card>

      {/* Ticket */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Key className="h-4 w-4" />
            Ticket ChileCompra
          </CardTitle>
        </CardHeader>
        <CardContent>
          {cuenta.empresa?.tiene_ticket ? (
            <div className="flex items-center gap-2">
              <Badge
                className="bg-green-100 text-green-800 hover:bg-green-100"
                variant="outline"
              >
                Ticket activo
              </Badge>
              <span className="text-xs text-muted-foreground">
                (los últimos dígitos se muestran en el perfil de empresa)
              </span>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Esta cuenta no tiene ticket de ChileCompra cargado. Sin él, no
                puede consultar licitaciones.
              </p>
              <form
                onSubmit={handleSubmit(onSubmitTicket)}
                className="space-y-3"
              >
                <div className="space-y-1.5">
                  <Label htmlFor="ticket">Ticket de ChileCompra</Label>
                  <Input
                    id="ticket"
                    type="text"
                    placeholder="Pegá el ticket completo aquí"
                    className="font-mono text-sm"
                    {...register("ticket")}
                  />
                  {errors.ticket && (
                    <p className="text-xs text-destructive">
                      {errors.ticket.message}
                    </p>
                  )}
                </div>
                <Button type="submit" size="sm" disabled={isSubmitting}>
                  {isSubmitting ? "Cargando..." : "Cargar ticket"}
                </Button>
              </form>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
