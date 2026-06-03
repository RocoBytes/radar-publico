"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { es } from "date-fns/locale";
import { Plus, ChevronLeft, ChevronRight } from "lucide-react";
import { getCuentas } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { UserStatus } from "@/types/admin";

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

function TicketBadge({ tieneTicket }: { tieneTicket: boolean }) {
  if (tieneTicket) {
    return (
      <Badge className="bg-green-100 text-green-800 hover:bg-green-100" variant="outline">
        Cargado
      </Badge>
    );
  }
  return (
    <Badge className="bg-red-100 text-red-800 hover:bg-red-100" variant="outline">
      Sin ticket
    </Badge>
  );
}

function TableSkeleton() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell><Skeleton className="h-4 w-40" /></TableCell>
          <TableCell><Skeleton className="h-4 w-32" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-5 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-8 w-12" /></TableCell>
        </TableRow>
      ))}
    </>
  );
}

export function CuentasListClient() {
  const [page, setPage] = useState(1);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["cuentas", page],
    queryFn: () => getCuentas(page),
  });

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {data ? `${data.total} cuenta${data.total !== 1 ? "s" : ""} en total` : ""}
        </p>
        <Button asChild size="sm">
          <Link href="/cuentas/nueva">
            <Plus className="h-4 w-4 mr-1.5" />
            Nueva cuenta
          </Link>
        </Button>
      </div>

      {isError && (
        <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          No se pudo cargar la lista de cuentas.
        </div>
      )}

      <div className="rounded-md border bg-background">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Email</TableHead>
              <TableHead>Empresa</TableHead>
              <TableHead>RUT</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Ticket</TableHead>
              <TableHead>Creado</TableHead>
              <TableHead className="w-16"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableSkeleton />
            ) : data?.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                  No hay cuentas registradas.
                </TableCell>
              </TableRow>
            ) : (
              data?.items.map((cuenta) => (
                <TableRow key={cuenta.id}>
                  <TableCell className="font-medium">{cuenta.email}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {cuenta.empresa?.razon_social ?? "Sin empresa"}
                  </TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs">
                    {cuenta.empresa?.rut ?? "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={cuenta.status} />
                  </TableCell>
                  <TableCell>
                    <TicketBadge tieneTicket={cuenta.empresa?.tiene_ticket ?? false} />
                  </TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {format(new Date(cuenta.created_at), "dd/MM/yyyy", { locale: es })}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/cuentas/${cuenta.id}`}>Ver</Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Paginación */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Página {page} de {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
            >
              Siguiente
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
