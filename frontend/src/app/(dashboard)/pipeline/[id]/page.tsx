import { PipelineItemClient } from "./_components/pipeline-item-client"

interface PipelineItemPageProps {
  params: Promise<{ id: string }>
}

export default async function PipelineItemPage({ params }: PipelineItemPageProps) {
  const { id } = await params
  return <PipelineItemClient id={id} />
}
