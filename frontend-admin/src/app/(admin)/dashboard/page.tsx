"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, Database, MessageSquare, DollarSign } from "lucide-react";
import { getAdminKpis } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

function formatCLP(n: number): string {
  return new Intl.NumberFormat("es-CL", {
    style: "currency",
    currency: "CLP",
    maximumFractionDigits: 0,
  }).format(n);
}

interface KpiCardProps {
  title: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  loading: boolean;
}

function KpiCard({ title, value, icon: Icon, loading }: KpiCardProps) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : (
          <p className="text-2xl font-bold">{value}</p>
        )}
      </CardContent>
    </Card>
  );
}

export default function AdminDashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin-kpis"],
    queryFn: getAdminKpis,
    refetchInterval: 60_000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          KPIs del sistema · actualiza cada 60s
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          title="Empresas activas"
          value={data ? String(data.empresas_activas) : "—"}
          icon={Building2}
          loading={isLoading}
        />
        <KpiCard
          title="Licitaciones indexadas"
          value={
            data ? data.licitaciones_indexadas.toLocaleString("es-CL") : "—"
          }
          icon={Database}
          loading={isLoading}
        />
        <KpiCard
          title="Mensajes IA hoy"
          value={data ? String(data.mensajes_ia_hoy) : "—"}
          icon={MessageSquare}
          loading={isLoading}
        />
        <KpiCard
          title="Costo IA (mes actual)"
          value={data ? formatCLP(data.costo_ia_mes) : "—"}
          icon={DollarSign}
          loading={isLoading}
        />
      </div>
    </div>
  );
}
