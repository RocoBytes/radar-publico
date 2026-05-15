"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAdminCostosIa } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

function formatCLP(n: number): string {
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(n);
}

const SKELETON_ROWS = [0, 1, 2, 3] as const;
const SKELETON_CELLS = [0, 1, 2, 3, 4] as const;

export default function CostosIaPage() {
  const [meses, setMeses] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["admin-costos-ia", meses],
    queryFn: () => getAdminCostosIa(meses),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Costos IA</h1>
          <p className="text-sm text-muted-foreground">
            Uso y costo estimado por empresa
          </p>
        </div>
        <Select
          value={String(meses)}
          onValueChange={(v) => setMeses(Number(v))}
        >
          <SelectTrigger className="w-36">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="1">Último mes</SelectItem>
            <SelectItem value="3">Últimos 3 meses</SelectItem>
            <SelectItem value="6">Últimos 6 meses</SelectItem>
            <SelectItem value="12">Último año</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Empresa</TableHead>
              <TableHead className="text-right">Mensajes</TableHead>
              <TableHead className="text-right">Tokens entrada</TableHead>
              <TableHead className="text-right">Tokens salida</TableHead>
              <TableHead className="text-right">Costo (USD)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              SKELETON_ROWS.map((rowKey) => (
                <TableRow key={rowKey}>
                  {SKELETON_CELLS.map((cellKey) => (
                    <TableCell key={cellKey}>
                      <Skeleton className="h-4 w-full" />
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : !data || data.empresas.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="py-8 text-center text-sm text-muted-foreground"
                >
                  Sin registros de uso de IA en el período seleccionado
                </TableCell>
              </TableRow>
            ) : (
              data.empresas.map((e) => (
                <TableRow key={e.empresa_id}>
                  <TableCell className="font-medium">{e.razon_social}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {e.mensajes_mes}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {e.tokens_input_mes.toLocaleString("es-CL")}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {e.tokens_output_mes.toLocaleString("es-CL")}
                  </TableCell>
                  <TableCell className="text-right font-mono text-xs">
                    {formatCLP(e.costo_mes)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
