"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ChatPanel } from "@/components/chat/chat-panel";
import { AlertsPanel } from "@/components/alerts/alerts-panel";
import { NewsPanel } from "@/components/news/news-panel";
import { MarketSidebar } from "@/components/sidebar/market-sidebar";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { IndicatorsChart } from "@/components/indicators/IndicatorsChart"; // [Codex] nuevo
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { getIndicators, sendChatMessage } from "@/lib/api"; // [Codex] nuevo

export function DashboardPage() {
  const { user, loading, token, logout } = useAuth();
  const router = useRouter();

  const sidebarToken = useMemo(() => token ?? undefined, [token]);

  const [indicatorData, setIndicatorData] = useState<any | null>(null); // [Codex] nuevo
  const [indicatorInsights, setIndicatorInsights] = useState<string | null>(null); // [Codex] nuevo
  const [indicatorLoading, setIndicatorLoading] = useState(false); // [Codex] nuevo
  const [indicatorError, setIndicatorError] = useState<string | null>(null); // [Codex] nuevo

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  const loadIndicators = useCallback(
    async (opts?: { cancelled?: () => boolean }) => {
      if (!user) return;
      const isCancelled = () => opts?.cancelled?.() ?? false;

      setIndicatorLoading(true);
      setIndicatorError(null);
      setIndicatorInsights(null);

      try {
        const payload = await getIndicators(
          "crypto",
          "BTCUSDT",
          "1h",
          token ?? undefined,
        );
        if (isCancelled()) return;
        setIndicatorData(payload);

        try {
          const indicatorsSummary = JSON.stringify(payload.indicators).slice(0, 1800);
          const prompt = `Analiza los siguientes indicadores para ${payload.symbol} (${payload.interval}) y entrega conclusiones tácticas en viñetas: ${indicatorsSummary}`;
          const aiResponse = await sendChatMessage(
            [{ role: "user", content: prompt }],
            token ?? undefined,
            undefined,
            {
              symbol: payload.symbol,
              interval: (payload.interval as "1h" | "4h" | "1d") ?? "1h",
            }
          );
          if (isCancelled()) return;
          const assistantMessage = aiResponse.messages.at(-1);
          setIndicatorInsights(assistantMessage?.content ?? null);
        } catch (err) {
          console.error("AI insights error", err);
          if (!isCancelled()) {
            setIndicatorInsights(null);
          }
        }
      } catch (err) {
        if (!isCancelled()) {
          console.error(err);
          setIndicatorError(
            err instanceof Error
              ? err.message
              : "No se pudieron cargar los indicadores."
          );
        }
      } finally {
        if (!isCancelled()) {
          setIndicatorLoading(false);
        }
      }
    },
    [token, user]
  );

  useEffect(() => {
    let cancelled = false;
    if (user) {
      loadIndicators({ cancelled: () => cancelled });
    }
    return () => {
      cancelled = true;
    };
  }, [loadIndicators, user]);

  const handleRefreshIndicators = useCallback(() => {
    loadIndicators();
  }, [loadIndicators]); // [Codex] nuevo

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
          <div className="flex flex-col gap-6">
            {/* [Codex] nuevo - tarjeta de indicadores con insights AI */}
            <Card className="flex flex-col">
              <CardHeader className="flex items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg font-medium">
                  Indicadores clave (BTCUSDT)
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRefreshIndicators}
                  disabled={indicatorLoading}
                >
                  {indicatorLoading ? "Actualizando..." : "Actualizar"}
                </Button>
              </CardHeader>
              <CardContent className="pt-4">
                {indicatorError && (
                  <p className="text-sm text-destructive">{indicatorError}</p>
                )}
                {indicatorData && (
                  <IndicatorsChart
                    symbol={indicatorData.symbol}
                    interval={indicatorData.interval}
                    indicators={indicatorData.indicators}
                    series={indicatorData.series}
                    insights={indicatorInsights}
                    loading={indicatorLoading}
                    error={indicatorError}
                  />
                )}
                {!indicatorData && !indicatorError && (
                  <p className="text-sm text-muted-foreground">
                    {indicatorLoading
                      ? "Cargando indicadores en tiempo real..."
                      : "Aún no se han cargado indicadores."}
                  </p>
                )}
              </CardContent>
            </Card>
            <Card className="flex flex-col">
              <CardContent className="flex h-full flex-col gap-4 pt-6">
                <ChatPanel token={token ?? undefined} />
              </CardContent>
            </Card>
          </div>
          <div className="flex flex-col gap-6">
            <AlertsPanel token={token ?? undefined} />
            <NewsPanel token={token ?? undefined} />
          </div>
        </section>
      </main>
    </div>
  );
}
