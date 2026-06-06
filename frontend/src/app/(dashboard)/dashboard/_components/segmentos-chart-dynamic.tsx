"use client"

import dynamic from "next/dynamic"
import { Skeleton } from "@/components/ui/skeleton"

export const SegmentosChartDynamic = dynamic(
  () =>
    import("./segmentos-chart").then((m) => ({
      default: m.SegmentosChart,
    })),
  {
    ssr: false,
    loading: () => <Skeleton className="h-[348px] w-full" />,
  }
)
