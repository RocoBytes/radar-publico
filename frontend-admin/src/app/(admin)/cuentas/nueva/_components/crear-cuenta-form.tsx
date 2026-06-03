"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Copy, CheckCircle } from "lucide-react";
import { crearCuenta } from "@/lib/api";
import { ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { CuentaCreadaResponse } from "@/types/admin";

// Regex básica de RUT chileno: XX.XXX.XXX-X o XXXXXXXX-X
const RUT_REGEX = /^\d{1,2}(\.\d{3}){2}-[\dkK]$/;

const crearCuentaSchema = z.object({
  email: z.string().email("Email inválido"),
  rut: z
    .string()
    .regex(RUT_REGEX, "Formato inválido. Usá XX.XXX.XXX-X"),
  razon_social: z
    .string()
    .min(3, "Mínimo 3 caracteres")
    .max(200, "Máximo 200 caracteres"),
});

type CrearCuentaFormData = z.infer<typeof crearCuentaSchema>;

export function CrearCuentaForm() {
  const router = useRouter();
  const [cuentaCreada, setCuentaCreada] = useState<CuentaCreadaResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CrearCuentaFormData>({
    resolver: zodResolver(crearCuentaSchema),
  });

  async function onSubmit(data: CrearCuentaFormData) {
    setErrorMessage(null);
    try {
      const cuenta = await crearCuenta(data);
      setCuentaCreada(cuenta);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setErrorMessage("Ya existe una cuenta con ese email o RUT.");
        } else {
          setErrorMessage(err.detail);
        }
      } else {
        setErrorMessage("Error inesperado. Intentá de nuevo.");
      }
    }
  }

  async function copyPassword() {
    if (!cuentaCreada) return;
    await navigator.clipboard.writeText(cuentaCreada.temp_password);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function goToCuenta() {
    if (!cuentaCreada) return;
    router.push(`/cuentas/${cuentaCreada.id}`);
  }

  return (
    <>
      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="contacto@empresa.cl"
                {...register("email")}
              />
              {errors.email && (
                <p className="text-xs text-destructive">{errors.email.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="rut">RUT empresa</Label>
              <Input
                id="rut"
                type="text"
                placeholder="76.123.456-7"
                {...register("rut")}
              />
              {errors.rut && (
                <p className="text-xs text-destructive">{errors.rut.message}</p>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="razon_social">Razón social</Label>
              <Input
                id="razon_social"
                type="text"
                placeholder="Empresa Ejemplo SpA"
                {...register("razon_social")}
              />
              {errors.razon_social && (
                <p className="text-xs text-destructive">
                  {errors.razon_social.message}
                </p>
              )}
            </div>

            {errorMessage && (
              <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {errorMessage}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "Creando cuenta..." : "Crear cuenta"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Modal con contraseña temporal */}
      <Dialog open={cuentaCreada !== null} onOpenChange={() => null}>
        <DialogContent className="sm:max-w-md" onInteractOutside={(e) => e.preventDefault()}>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Cuenta creada exitosamente
            </DialogTitle>
            <DialogDescription>
              Guardá esta contraseña temporal — no se puede recuperar luego.
              Entregásela al cliente para que pueda iniciar sesión.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Email</p>
              <p className="text-sm font-medium">{cuentaCreada?.email}</p>
            </div>

            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Contraseña temporal</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 rounded-md bg-muted px-3 py-2 text-sm font-mono font-bold tracking-wider select-all">
                  {cuentaCreada?.temp_password}
                </code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void copyPassword()}
                >
                  {copied ? (
                    <CheckCircle className="h-4 w-4 text-green-600" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>

            <div className="rounded-md bg-yellow-50 border border-yellow-200 px-3 py-2 text-xs text-yellow-800">
              Esta contraseña solo se muestra una vez. No la cierres hasta
              haberla comunicado al cliente.
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button onClick={goToCuenta}>
              Ver cuenta
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
