import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EmpresaForm } from "./_components/empresa-form"
import { PreferenciasForm } from "./_components/preferencias-form"

export default function ConfiguracionPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Configuración</h1>
        <p className="text-muted-foreground text-sm mt-1">
          Administrá los datos de tu empresa y preferencias.
        </p>
      </div>
      <Tabs defaultValue="empresa">
        <TabsList>
          <TabsTrigger value="empresa">Empresa</TabsTrigger>
          <TabsTrigger value="notificaciones">Notificaciones</TabsTrigger>
        </TabsList>
        <TabsContent value="empresa" className="mt-6">
          <EmpresaForm />
        </TabsContent>
        <TabsContent value="notificaciones" className="mt-6">
          <PreferenciasForm />
        </TabsContent>
      </Tabs>
    </div>
  )
}
