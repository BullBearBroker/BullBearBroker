"use client";

import Link from "next/link";
import { memo, useMemo } from "react";
import { Menu, X } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { useOptionalUIState } from "@/hooks/useUIState";

const noop = () => undefined;

function NavbarComponent() {
  const { user, logout, loading } = useAuth();
  const uiState = useOptionalUIState();
  const sidebarOpen = uiState?.sidebarOpen ?? false;
  const toggleSidebar = uiState?.toggleSidebar ?? noop;

  const userLabel = useMemo(() => user?.name || user?.email || "Invitado", [user]);

  return (
    <header
      className="border-b bg-card/60 backdrop-blur supports-[backdrop-filter]:bg-card/80"
      role="banner"
    >
      <nav
        className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3"
        aria-label="Barra de navegación principal"
      >
        <Link
          href="/"
          className="text-lg font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        >
          BullBearBroker
        </Link>
        <div className="flex items-center gap-3">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="md:hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            aria-label={sidebarOpen ? "Cerrar panel de mercados" : "Abrir panel de mercados"}
            aria-expanded={sidebarOpen}
            aria-controls="market-sidebar"
            onClick={toggleSidebar}
          >
            {sidebarOpen ? (
              <X className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Menu className="h-4 w-4" aria-hidden="true" />
            )}
          </Button>
          {loading ? (
            <span className="text-sm text-muted-foreground" aria-live="polite">
              Verificando sesión...
            </span>
          ) : user ? (
            <div className="flex items-center gap-3">
              <span
                className="text-sm text-muted-foreground"
                aria-label={`Sesión iniciada como ${userLabel}`}
              >
                {userLabel}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                Cerrar sesión
              </Button>
            </div>
          ) : (
            <Button
              size="sm"
              asChild
              className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <Link href="/login">Ingresar</Link>
            </Button>
          )}
        </div>
      </nav>
    </header>
  );
}

export const Navbar = memo(NavbarComponent);
