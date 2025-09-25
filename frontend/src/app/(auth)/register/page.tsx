import Link from "next/link";

import { RegisterForm } from "@/components/forms/register-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function RegisterPage() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">Crear cuenta</CardTitle>
        <p className="text-sm text-muted-foreground">
          Regístrate para acceder al ecosistema BullBearBroker.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <RegisterForm />
        <p className="text-sm text-muted-foreground">
          ¿Ya tienes cuenta?{" "}
          <Link href="/login" className="text-primary hover:underline">
            Inicia sesión aquí
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
