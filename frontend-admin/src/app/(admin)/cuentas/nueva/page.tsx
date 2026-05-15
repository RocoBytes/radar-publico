import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CrearCuentaForm } from "./_components/crear-cuenta-form";

export default function NuevaCuentaPage() {
  return (
    <div className="space-y-6 max-w-lg">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/cuentas">
            <ChevronLeft className="h-4 w-4 mr-1" />
            Volver a cuentas
          </Link>
        </Button>
      </div>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Nueva cuenta</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Creá una cuenta para un nuevo proveedor del Estado.
        </p>
      </div>
      <CrearCuentaForm />
    </div>
  );
}
