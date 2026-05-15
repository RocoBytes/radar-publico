"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const loginSchema = z.object({
  email: z.string().email("Email inválido"),
  password: z.string().min(1, "La contraseña es obligatoria"),
});

type LoginFormData = z.infer<typeof loginSchema>;

type LoginApiResponse = {
  must_change_password?: boolean;
  detail?: string;
};

export function LoginForm() {
  const router = useRouter();
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [mustChangePassword, setMustChangePassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
  });

  async function onSubmit(data: LoginFormData) {
    setErrorMessage(null);
    setMustChangePassword(false);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
      });

      const json = (await res.json()) as LoginApiResponse;

      if (res.status === 403) {
        setErrorMessage("Acceso denegado — solo administradores.");
        return;
      }

      if (!res.ok) {
        setErrorMessage(
          json.detail ?? "Credenciales inválidas. Verificá tus datos."
        );
        return;
      }

      if (json.must_change_password) {
        setMustChangePassword(true);
        return;
      }

      router.push("/cuentas");
    } catch {
      setErrorMessage("Error de conexión. Intentá de nuevo.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Iniciar sesión</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="admin@radarpublico.cl"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-xs text-destructive">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password">Contraseña</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-xs text-destructive">
                {errors.password.message}
              </p>
            )}
          </div>

          {errorMessage && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {errorMessage}
            </div>
          )}

          {mustChangePassword && (
            <div className="rounded-md bg-yellow-50 px-3 py-2 text-sm text-yellow-800 border border-yellow-200">
              Debés cambiar tu contraseña antes de continuar. Contactá al
              equipo técnico.
            </div>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? "Ingresando..." : "Ingresar"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
