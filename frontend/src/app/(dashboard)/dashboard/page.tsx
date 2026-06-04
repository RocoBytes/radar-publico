import dynamic from "next/dynamic"
import { KpiCards } from "./_components/kpi-cards"
import { TopOportunidades } from "./_components/top-oportunidades"
import { CierresProximos } from "./_components/cierres-proximos"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * SegmentosChart usa recharts (~400 kB). Se carga de forma lazy para que
 * recharts no entre en el bundle inicial del dashboard.
 * ssr: false porque recharts usa APIs del DOM que no existen en el servidor.
 */
const SegmentosChart = dynamic(
  () =>
    import("./_components/segmentos-chart").then((m) => ({
      default: m.SegmentosChart,
    })),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[348px] w-full" />,
  }
)

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
