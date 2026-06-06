import { SegmentosResumen } from "./_components/segmentos-resumen"
import { TendenciaChartDynamic, TopOrganismosChartDynamic } from "./_components/charts-dynamic"

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
        <TendenciaChartDynamic />
        <TopOrganismosChartDynamic />
      </div>
      <SegmentosResumen />
    </div>
  )
}
