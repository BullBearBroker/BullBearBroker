"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/providers/auth-provider";
import { ChatPanel } from "@/components/chat/chat-panel";
import { AlertsPanel } from "@/components/alerts/alerts-panel";
import { NewsPanel } from "@/components/news/news-panel";
import { PortfolioPanel } from "@/components/portfolio/PortfolioPanel";
import { MarketSidebar } from "@/components/sidebar/market-sidebar";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
import { IndicatorsChart } from "@/components/indicators/IndicatorsChart"; // [Codex] nuevo
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getIndicators, sendChatMessage } from "@/lib/api"; // [Codex] nuevo
import { usePushNotifications } from "@/hooks/usePushNotifications";
// 🧩 Bloque 8B
import NotificationCenterCard from "@/components/dashboard/notification-center-card";
import { useHistoricalData } from "@/hooks/useHistoricalData"; // [Codex] nuevo
import { useRealtime } from "@/hooks/useRealtime"; // ✅ Codex fix: integración realtime en dashboard
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { ScrollArea } from "@/components/ui/scroll-area";

function DashboardPageContent() {
  const { user, loading, token, logout } = useAuth();
  const router = useRouter();

  const sidebarToken = useMemo(() => token ?? undefined, [token]);

  const {
    enabled: pushEnabled,
    error: pushError,
    permission: pushPermission,
    loading: pushLoading,
    testing: pushTesting,
    events: pushEvents,
    logs: pushLogs,
    sendTestNotification,
    requestPermission: requestPushPermission,
    dismissEvent: dismissPushEvent,
  } = usePushNotifications(token ?? undefined);

  const { connected: realtimeConnected, data: realtimeData } = useRealtime(); // ✅ Codex fix: estado de conexión realtime

  const [indicatorData, setIndicatorData] = useState<any | null>(null); // [Codex] nuevo
  const [indicatorSymbol, setIndicatorSymbol] = useState("BTCUSDT"); // [Codex] nuevo
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
          indicatorSymbol,
          "1h",
          token ?? undefined,
        );
        if (isCancelled()) return;
        setIndicatorData(payload);
        if (payload?.symbol) {
          setIndicatorSymbol(payload.symbol);
        }

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
    [indicatorSymbol, token, user]
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

  const historicalInterval = indicatorData?.interval ?? "1h"; // [Codex] nuevo
  const historicalMarket = (indicatorData?.type as "auto" | "crypto" | "stock" | "equity" | "forex" | undefined) ?? "auto"; // [Codex] nuevo

  const realtimeHighlight = useMemo(() => {
    if (!realtimeData || typeof realtimeData !== "object") {
      return null;
    }

    const payload = realtimeData as Record<string, unknown>;
    const type = typeof payload.type === "string" ? payload.type : null;

    if (type === "price" && typeof payload.symbol === "string") {
      const rawPrice = payload.price;
      const numericPrice =
        typeof rawPrice === "number"
          ? rawPrice
          : typeof rawPrice === "string"
          ? Number(rawPrice)
          : null;

      if (numericPrice !== null && Number.isFinite(numericPrice)) {
        return `${payload.symbol} → $${numericPrice.toLocaleString(undefined, {
          maximumFractionDigits: 2,
        })}`;
      }
    }

    if (type === "insight") {
      const content =
        typeof payload.content === "string"
          ? payload.content
          : typeof payload.message === "string"
          ? payload.message
          : null;

      if (content) {
        if (typeof payload.symbol === "string") {
          return `${payload.symbol} → ${content}`;
        }
        return content;
      }
    }

    if (typeof payload.message === "string") {
      return payload.message;
    }

    return null;
  }, [realtimeData]); // ✅ Codex fix: resumen legible del último evento

  const {
    data: historicalData,
    error: historicalError,
    isLoading: historicalLoading,
    isValidating: historicalValidating,
    refresh: refreshHistorical,
  } = useHistoricalData(indicatorSymbol, {
    interval: historicalInterval,
    market: historicalMarket,
    limit: 240,
  }); // [Codex] nuevo

  const handleRefreshIndicators = useCallback(() => {
    loadIndicators();
    refreshHistorical();
  }, [loadIndicators, refreshHistorical]); // [Codex] nuevo

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
    <div
      className="grid min-h-screen bg-background text-foreground md:grid-cols-[280px_1fr]"
      data-testid="dashboard-shell"
    >
      <aside className="border-r bg-card/50">
        <MarketSidebar token={sidebarToken} user={user} onLogout={logout} />
      </aside>
      <main className="flex flex-col gap-6 p-4 lg:p-6" data-testid="dashboard-content">
        <header className="flex flex-col gap-4 rounded-lg border bg-card p-4 shadow-sm md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-sm text-muted-foreground">Bienvenido de vuelta</p>
            <h1 className="text-2xl font-semibold">{user.name || user.email}</h1>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={pushEnabled ? "outline" : "secondary"} className="hidden md:inline-flex">
              {pushEnabled ? "Push activo" : "Push inactivo"}
            </Badge>
            <ThemeToggle />
            <Button variant="outline" onClick={logout}>
              Cerrar sesión
            </Button>
          </div>
        </header>
        <div className="flex flex-col gap-3">
          {pushError && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              {pushError}
            </div>
          )}
          // 🧩 Bloque 8B
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <NotificationCenterCard />
            <Card data-testid="notification-center" className="border-dashed">
              <CardHeader className="flex flex-col gap-1 pb-3">
                <CardTitle className="text-base font-semibold">Centro de notificaciones</CardTitle>
                <CardDescription>
                  Gestiona las alertas en tiempo real provenientes del dispatcher.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={pushEnabled ? "default" : "secondary"}>
                    {pushEnabled ? "Suscripción activa" : pushLoading ? "Sincronizando..." : "Suscripción inactiva"}
                  </Badge>
                  {pushPermission !== "unsupported" && pushPermission !== "granted" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void requestPushPermission()}
                      disabled={pushLoading}
                    >
                      Activar notificaciones
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void sendTestNotification()}
                    disabled={!pushEnabled || pushTesting}
                  >
                    {pushTesting ? "Enviando prueba..." : "Enviar prueba"}
                  </Button>
                </div>
                <div className="space-y-2" aria-live="polite">
                  {pushEvents.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Aún no se reciben notificaciones. Envía una prueba para verificar el canal.
                    </p>
                  ) : (
                    pushEvents
                      .slice()
                      .reverse()
                      .map((event) => (
                        <div
                          key={event.id}
                          className="flex items-start justify-between gap-3 rounded-md border border-border/60 bg-muted/40 p-3"
                        >
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-foreground">{event.title}</p>
                            {event.body && (
                              <p className="text-sm text-muted-foreground">{event.body}</p>
                            )}
                            <p className="text-xs text-muted-foreground">
                              {new Date(event.receivedAt).toLocaleString()}
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="-mr-1"
                            onClick={() => dismissPushEvent(event.id)}
                          >
                            Cerrar
                          </Button>
                        </div>
                      ))
                  )}
                </div>
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Registro de eventos
                  </p>
                  <ScrollArea className="h-32 rounded-md border border-border/60 bg-muted/20 p-2">
                    {pushLogs.length === 0 ? (
                      <p className="text-xs text-muted-foreground">
                        Esperando eventos auditables del dispatcher...
                      </p>
                    ) : (
                      <ul className="space-y-1 text-xs text-foreground">
                        {pushLogs
                          .slice()
                          .reverse()
                          .map((log, index) => (
                            <li key={`${log}-${index}`}>{log}</li>
                          ))}
                      </ul>
                    )}
                  </ScrollArea>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
        <div className="p-2 text-xs">
          <span className={realtimeConnected ? "text-green-500" : "text-red-500"}>
            {realtimeConnected ? "🟢 Conectado a Realtime" : "🔴 Desconectado"}
          </span>
          {realtimeHighlight && (
            <p className="mt-1 text-foreground">{realtimeHighlight}</p>
          )}
          {realtimeData && (
            <pre className="text-gray-400 mt-2">
              {JSON.stringify(realtimeData, null, 2)}
            </pre>
          )}
        </div>
        <section
          className="grid flex-1 gap-6 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]"
          data-testid="dashboard-modules"
        >
          <div className="grid auto-rows-min gap-6">
            <PortfolioPanel token={token ?? undefined} />
            {/* [Codex] nuevo - tarjeta de indicadores con insights AI */}
            <Card className="flex flex-col" data-testid="dashboard-indicators">
              <CardHeader className="flex items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-lg font-medium">
                  Indicadores clave ({indicatorSymbol})
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleRefreshIndicators}
                  disabled={indicatorLoading || historicalLoading || historicalValidating}
                >
                  {indicatorLoading || historicalLoading || historicalValidating
                    ? "Actualizando..."
                    : "Actualizar"}
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
                    history={historicalData}
                    historyError={historicalError?.message ?? null}
                    historyLoading={historicalLoading || historicalValidating}
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
            <Card className="flex flex-col" data-testid="dashboard-chat">
              <CardHeader className="pb-2">
                <CardTitle className="text-lg font-medium">Asistente estratégico</CardTitle>
                <CardDescription>
                  Conversa con el bot para contextualizar las señales del mercado.
                </CardDescription>
              </CardHeader>
              <CardContent className="flex h-full flex-col gap-4">
                <ChatPanel token={token ?? undefined} />
              </CardContent>
            </Card>
          </div>
          <div className="grid auto-rows-min gap-6">
            <AlertsPanel token={token ?? undefined} />
            <NewsPanel token={token ?? undefined} />
          </div>
        </section>
      </main>
    </div>
  );
}

function DashboardPageFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-md rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-center">
        <h2 className="text-lg font-semibold text-destructive">No se pudo cargar el dashboard</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Actualiza la página o intenta iniciar sesión nuevamente.
        </p>
      </div>
    </div>
  );
}

export function DashboardPage() {
  return (
    <ErrorBoundary fallback={<DashboardPageFallback />}>
      <DashboardPageContent />
    </ErrorBoundary>
  );
}
