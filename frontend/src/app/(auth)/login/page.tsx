import Link from "next/link";

import LoginForm from "@/components/forms/login-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader>
        <CardTitle className="text-2xl font-semibold">Iniciar sesión</CardTitle>
        <p className="text-sm text-muted-foreground">
          Accede a tu panel financiero inteligente.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <LoginForm />
        <p className="text-sm text-muted-foreground">
          ¿No tienes cuenta?{" "}
          <Link href="/register" className="text-primary hover:underline">
            Regístrate aquí
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
