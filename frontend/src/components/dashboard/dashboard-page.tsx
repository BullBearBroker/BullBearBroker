"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ChatPanel } from "@/components/chat/chat-panel";
import { AlertsPanel } from "@/components/alerts/alerts-panel";
import { NewsPanel } from "@/components/news/news-panel";
import { MarketSidebar } from "@/components/sidebar/market-sidebar";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function DashboardPage() {
  const { user, loading, accessToken, logout } = useAuth();
  const router = useRouter();

  const sidebarToken = useMemo(() => accessToken ?? undefined, [accessToken]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Cargando sesión...</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Redirigiendo al acceso...</p>
      </div>
    );
  }

  return (
    <div className="grid min-h-screen bg-background text-foreground md:grid-cols-[300px_1fr]">
      <aside className="border-r bg-card/50">
        <MarketSidebar token={sidebarToken} user={user} onLogout={logout} />
      </aside>
      <main className="flex flex-col gap-6 p-6">
        <header className="flex flex-col gap-4 rounded-lg border bg-card p-4 shadow-sm md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Bienvenido de vuelta</p>
            <h1 className="text-2xl font-semibold">{user.name || user.email}</h1>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Button variant="outline" onClick={logout}>
              Cerrar sesión
            </Button>
          </div>
        </header>
        <section className="grid flex-1 gap-6 xl:grid-cols-[2fr_1fr]">
          <Card className="flex flex-col">
            <CardContent className="flex h-full flex-col gap-4 pt-6">
              <ChatPanel token={accessToken ?? undefined} />
            </CardContent>
          </Card>
          <div className="flex flex-col gap-6">
            <AlertsPanel token={accessToken ?? undefined} />
            <NewsPanel token={accessToken ?? undefined} />
          </div>
        </section>
      </main>
    </div>
  );
}
