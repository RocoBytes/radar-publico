"use client"

import dynamic from "next/dynamic"
import { Skeleton } from "@/components/ui/skeleton"

const loading = () => <Skeleton className="h-[348px] w-full" />

export const TendenciaChartDynamic = dynamic(
  () => import("./tendencia-chart").then((m) => ({ default: m.TendenciaChart })),
  { ssr: false, loading }
)

export const TopOrganismosChartDynamic = dynamic(
  () =>
    import("./top-organismos-chart").then((m) => ({
      default: m.TopOrganismosChart,
    })),
  { ssr: false, loading }
)
