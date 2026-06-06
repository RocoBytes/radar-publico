import { Suspense } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { KpiCards } from "./_components/kpi-cards"
import { TopOportunidades } from "./_components/top-oportunidades"
import { CierresProximos } from "./_components/cierres-proximos"
import { SegmentosChartDynamic } from "./_components/segmentos-chart-dynamic"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Resumen de tu actividad comercial</p>
      </div>
      <Suspense
        fallback={
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-lg" />
            ))}
          </div>
        }
      >
        <KpiCards />
      </Suspense>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Suspense fallback={<Skeleton className="h-64 rounded-lg" />}>
            <SegmentosChartDynamic />
          </Suspense>
        </div>
        <Suspense fallback={<Skeleton className="h-64 rounded-lg" />}>
          <TopOportunidades />
        </Suspense>
      </div>
      <Suspense fallback={<Skeleton className="h-48 rounded-lg" />}>
        <CierresProximos />
      </Suspense>
    </div>
  )
}
