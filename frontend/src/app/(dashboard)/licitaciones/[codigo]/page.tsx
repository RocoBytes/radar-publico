import { LicitacionDetalleClient } from "./_components/licitacion-detalle-client"

interface LicitacionDetallePageProps {
  params: Promise<{ codigo: string }>
}

export default async function LicitacionDetallePage({
  params,
}: LicitacionDetallePageProps) {
  const { codigo } = await params
  return <LicitacionDetalleClient codigo={decodeURIComponent(codigo)} />
}
