import dynamic from "next/dynamic"
import { SegmentosResumen } from "./_components/segmentos-resumen"
import { Skeleton } from "@/components/ui/skeleton"

/**
 * TendenciaChart y TopOrganismosChart usan recharts (~400 kB).
 * Se cargan de forma lazy para que recharts no entre en el bundle inicial
 * de la página de análisis.
 * ssr: false porque recharts usa APIs del DOM que no existen en el servidor.
 */
const TendenciaChart = dynamic(
  () =>
    import("./_components/tendencia-chart").then((m) => ({
      default: m.TendenciaChart,
    })),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[348px] w-full" />,
  }
)

const TopOrganismosChart = dynamic(
  () =>
    import("./_components/top-organismos-chart").then((m) => ({
      default: m.TopOrganismosChart,
    })),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[348px] w-full" />,
  }
)

export default function AnalisisPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Análisis de mercado
        </h1>
        <p className="text-muted-foreground text-sm mt-1">
          Tendencias y distribución de licitaciones del Mercado Público.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <TendenciaChart />
        <TopOrganismosChart />
      </div>
      <SegmentosResumen />
    </div>
  )
}
