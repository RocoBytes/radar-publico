import { redirect } from "next/navigation";
import { getAdminUser } from "@/lib/auth";
import { LoginForm } from "./_components/login-form";

export default async function LoginPage() {
  const user = await getAdminUser();

  if (user) {
    redirect("/cuentas");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Radar Público</h1>
          <p className="mt-1 text-sm text-muted-foreground">Panel de administración</p>
        </div>
        <LoginForm />
      </div>
    </div>
  );
}
