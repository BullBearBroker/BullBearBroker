"use client";

import Link from "next/link";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";

export function Navbar() {
  const { user, logout, loading } = useAuth();

  return (
    <header className="border-b bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <nav className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/" className="text-lg font-semibold">
          BullBearBroker
        </Link>
        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-sm text-muted-foreground">Verificando sesión...</span>
          ) : user ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">
                {user.name || user.email}
              </span>
              <Button variant="outline" size="sm" onClick={logout}>
                Cerrar sesión
              </Button>
            </div>
          ) : (
            <Button size="sm" asChild>
              <Link href="/login">Ingresar</Link>
            </Button>
          )}
        </div>
      </nav>
    </header>
  );
}
