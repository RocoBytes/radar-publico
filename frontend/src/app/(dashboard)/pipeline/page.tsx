import { PipelineListClient } from "./_components/pipeline-list-client"

export default function PipelinePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Pipeline</h1>
        <p className="text-sm text-muted-foreground">
          Licitaciones que estás siguiendo activamente
        </p>
      </div>
      <PipelineListClient />
    </div>
  )
}
