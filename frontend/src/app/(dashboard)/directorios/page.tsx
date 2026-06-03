import { Suspense } from "react"
import { DirectoriosClient } from "./_components/directorios-client"
import { Skeleton } from "@/components/ui/skeleton"

export default function DirectoriosPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Directorios</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Organismos compradores y proveedores activos en Mercado Público (últimos 2 años).
        </p>
      </div>
      <Suspense fallback={<Skeleton className="h-96 w-full" />}>
        <DirectoriosClient />
      </Suspense>
    </div>
  )
}
