import { CuentasListClient } from "./_components/cuentas-list-client";

export default function CuentasPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Gestión de cuentas</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Administrá las cuentas de empresas proveedoras del Estado.
        </p>
      </div>
      <CuentasListClient />
    </div>
  );
}
