import { RadaresClient } from "./_components/radares-client"

export default function RadaresPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Radares</h1>
        <p className="text-sm text-muted-foreground">
          Monitoreo automático de nuevas licitaciones según tus criterios
        </p>
      </div>
      <RadaresClient />
    </div>
  )
}
