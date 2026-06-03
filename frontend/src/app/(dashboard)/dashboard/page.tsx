import { KpiCards } from "./_components/kpi-cards"
import { SegmentosChart } from "./_components/segmentos-chart"
import { TopOportunidades } from "./_components/top-oportunidades"
import { CierresProximos } from "./_components/cierres-proximos"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Resumen de tu actividad comercial</p>
      </div>
      <KpiCards />
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <SegmentosChart />
        </div>
        <TopOportunidades />
      </div>
      <CierresProximos />
    </div>
  )
}
