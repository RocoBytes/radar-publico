import { LicitacionesListClient } from "./_components/licitaciones-list-client"

export default function LicitacionesPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Oportunidades</h1>
        <p className="text-sm text-muted-foreground">
          Licitaciones activas y recientes del Mercado Público
        </p>
      </div>
      <LicitacionesListClient />
    </div>
  )
}
