"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { PortfolioPanel } from "@/components/portfolio/PortfolioPanel";

export default function PortfolioPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Cargando portafolio...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <p className="text-muted-foreground">Redirigiendo al acceso...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background p-6 text-foreground">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
        <header className="space-y-1">
          <p className="text-sm text-muted-foreground">Gestiona tus posiciones</p>
          <h1 className="text-3xl font-semibold">Tu portafolio</h1>
        </header>
        <PortfolioPanel token={token ?? undefined} />
      </div>
    </div>
  );
}
