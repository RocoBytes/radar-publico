import { CuentaDetailClient } from "./_components/cuenta-detail-client";

type Params = {
  params: Promise<{ id: string }>;
};

export default async function CuentaDetailPage({ params }: Params) {
  const { id } = await params;
  return <CuentaDetailClient id={id} />;
}
