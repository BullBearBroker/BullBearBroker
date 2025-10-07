"use client";

import dynamic from "next/dynamic";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "@/lib/motion";
import { Activity, BellRing, Bot, LineChart, Newspaper, Radio, SignalHigh, Wallet } from "lucide-react";

import { useAuth } from "@/components/providers/auth-provider";
import { MarketSidebar } from "@/components/sidebar/market-sidebar";
import { ThemeToggle } from "@/components/dashboard/theme-toggle";
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
import { Skeleton } from "@/components/common/Skeleton";
import { cn } from "@/lib/utils";
import { useOptionalUIState } from "@/hooks/useUIState";

const noopCallback = () => undefined;

function PanelSkeleton({
  lines = 3,
  "aria-label": ariaLabel,
}: {
  lines?: number;
  "aria-label"?: string;
}) {
  return (
    <div className="space-y-3" aria-label={ariaLabel} aria-live="polite">
      {Array.from({ length: lines }).map((_, index) => (
        <Skeleton key={`panel-skeleton-${index}`} className="h-3 w-full" />
      ))}
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="space-y-4" aria-busy aria-live="polite">
      <Skeleton className="h-9 w-48" />
      <div className="space-y-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={`chart-skeleton-${index}`} className="h-3 w-full" />
        ))}
      </div>
      <Skeleton className="h-56 w-full" />
    </div>
  );
}

const cardMotionProps = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: 12 },
  transition: { duration: 0.24, ease: "easeOut" },
} as const;

const overlayMotionProps = {
  initial: { opacity: 0 },
  animate: { opacity: 1 },
  exit: { opacity: 0 },
  transition: { duration: 0.2 },
} as const;

const createCardMotion = (delay = 0) => ({
  ...cardMotionProps,
  transition: { ...cardMotionProps.transition, delay },
});

function AsyncModuleFallback({
  title,
  description,
  icon,
  className,
  "aria-label": ariaLabel,
}: {
  title: string;
  description: string;
  icon: ReactNode;
  className?: string;
  "aria-label"?: string;
}) {
  return (
    <Card
      className={cn("surface-card flex flex-col", className)}
      aria-label={ariaLabel}
      aria-live="polite"
    >
      <CardHeader className="space-y-2 pb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
          {icon} {title}
        </CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <PanelSkeleton aria-label={`Cargando ${title.toLowerCase()}`} lines={4} />
      </CardContent>
    </Card>
  );
}

const IndicatorsChart = dynamic(
  () => import("@/components/indicators/IndicatorsChart"),
  {
    ssr: false,
    loading: () => <ChartSkeleton />,
  },
);

const AlertsPanel = dynamic(
  () =>
    import("@/components/alerts/alerts-panel").then((mod) => ({
      default: mod.AlertsPanel,
    })),
  {
    ssr: false,
    suspense: true,
  },
);

const NewsPanel = dynamic(
  () => import("@/components/news/NewsPanel"),
  {
    ssr: false,
    loading: () => (
      <AsyncModuleFallback
        title="Noticias"
        description="Cargando el pulso del mercado..."
        icon={<Newspaper className="h-5 w-5 text-primary" aria-hidden="true" />}
        aria-label="Sección de noticias cargándose"
        className="h-full"
      />
    ),
  },
);

const ChatPanel = dynamic(
  () =>
    import("@/components/chat/chat-panel").then((mod) => ({
      default: mod.ChatPanel,
    })),
  {
    ssr: false,
    suspense: true,
  },
);

const PortfolioPanel = dynamic(
  () => import("@/components/portfolio/PortfolioPanel"),
  {
    ssr: false,
    loading: () => (
      <AsyncModuleFallback
        title="Portafolio"
        description="Cargando el resumen de tus posiciones..."
        icon={<Wallet className="h-5 w-5 text-primary" aria-hidden="true" />}
        aria-label="Sección de portafolio cargándose"
        className="h-full"
      />
    ),
  },
);

function DashboardPageContent() {
  const { user, loading, token, logout } = useAuth();
  const router = useRouter();
  const uiState = useOptionalUIState();
  const sidebarOpen = uiState?.sidebarOpen ?? false;
  const closeSidebar = uiState?.closeSidebar ?? noopCallback;
  const resolveDesktopPreference = useCallback(() => {
    if (typeof window === "undefined") {
      return true;
    }

    const minimumWidth = 768;
    const widthFallback = typeof window.innerWidth === "number" ? window.innerWidth >= minimumWidth : true;

    if (typeof window.matchMedia === "function") {
      const mediaQuery = window.matchMedia("(min-width: 768px)");
      if (typeof mediaQuery.matches === "boolean") {
        return mediaQuery.matches || widthFallback;
      }
    }

    return widthFallback;
  }, []);

  const [isDesktop, setIsDesktop] = useState<boolean>(() => resolveDesktopPreference());

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
  const sidebarVariants = useMemo(
    () => ({
      hidden: {
        x: isDesktop ? 0 : -320,
        opacity: isDesktop ? 1 : 0,
        pointerEvents: isDesktop ? "auto" : "none",
      },
      visible: {
        x: 0,
        opacity: 1,
        pointerEvents: "auto",
      },
    }),
    [isDesktop],
  );
  const shouldShowOverlay = sidebarOpen && !isDesktop;

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, router, user]);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }

    const minimumWidth = 768;
    const mediaQuery = window.matchMedia("(min-width: 768px)");

    const computeDesktopState = (matches: boolean) => {
      if (matches) {
        return true;
      }
      if (typeof window.innerWidth === "number") {
        return window.innerWidth >= minimumWidth;
      }
      return false;
    };

    setIsDesktop(computeDesktopState(mediaQuery.matches));

    const listener = (event: MediaQueryListEvent) => {
      setIsDesktop(computeDesktopState(event.matches));
    };

    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", listener);
      return () => {
        mediaQuery.removeEventListener("change", listener);
      };
    }

    if (typeof mediaQuery.addListener === "function") {
      mediaQuery.addListener(listener);
      return () => {
        mediaQuery.removeListener(listener);
      };
    }

    return () => undefined;
  }, []);

  useEffect(() => {
    if (!sidebarOpen) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeSidebar();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [closeSidebar, sidebarOpen]);

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
      <AnimatePresence>
        {shouldShowOverlay ? (
          <motion.div
            {...overlayMotionProps}
            className="fixed inset-0 z-30 bg-background/70 backdrop-blur-sm md:hidden"
            role="presentation"
            aria-hidden="true"
            onClick={closeSidebar}
          />
        ) : null}
      </AnimatePresence>
      <motion.aside
        id="market-sidebar"
        role="complementary"
        aria-label="Panel de mercados y navegación secundaria"
        aria-hidden={!(sidebarOpen || isDesktop)}
        tabIndex={sidebarOpen || isDesktop ? 0 : -1}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex h-full w-72 flex-col overflow-y-auto border-r border-border/60 bg-card/90 shadow-xl backdrop-blur-lg",
          "md:relative md:z-auto md:w-full md:border-r md:bg-card/60 md:shadow-none md:backdrop-blur",
        )}
        variants={sidebarVariants}
        initial={isDesktop ? "visible" : "hidden"}
        animate={sidebarOpen || isDesktop ? "visible" : "hidden"}
        transition={{ duration: 0.24, ease: "easeOut" }}
        data-state={sidebarOpen ? "open" : "closed"}
      >
        <MarketSidebar token={sidebarToken} user={user} onLogout={logout} />
      </motion.aside>
      <main
        className="flex flex-col gap-6 p-4 md:p-6"
        data-testid="dashboard-content"
        role="main"
        aria-label="Panel principal del dashboard"
      >
        <motion.header
          className="surface-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between"
          {...cardMotionProps}
        >
          <div>
            <p className="text-sm text-muted-foreground">Bienvenido de vuelta</p>
            <h1 className="text-2xl font-sans font-semibold tracking-tight">
              {user.name || user.email}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3" aria-live="polite">
            <Badge
              variant={pushEnabled ? "outline" : "secondary"}
              className="hidden rounded-full px-3 py-1 text-xs font-medium md:inline-flex"
            >
              {pushEnabled ? "Push activo" : "Push inactivo"}
            </Badge>
            <ThemeToggle />
            <Button
              variant="outline"
              onClick={logout}
              className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              Cerrar sesión
            </Button>
          </div>
        </motion.header>
        <div className="flex flex-col gap-4">
          <AnimatePresence initial={false}>
            {pushError ? (
              <motion.div
                key="push-error"
                role="alert"
                className="rounded-2xl border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive shadow-sm"
                {...createCardMotion(0.12)}
              >
                {pushError}
              </motion.div>
            ) : null}
          </AnimatePresence>
          {/* 🧩 Bloque 8B */}
          <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
            <motion.div className="h-full" {...createCardMotion(0.08)}>
              <NotificationCenterCard />
            </motion.div>
            <motion.div className="h-full" {...createCardMotion(0.12)}>
              <Card data-testid="notification-center" className="surface-card">
                <CardHeader className="space-y-2 pb-4">
                  <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
                    <BellRing className="h-5 w-5 text-primary" aria-hidden="true" /> Preferencias de alerta
                  </CardTitle>
                  <CardDescription>
                    Gestiona las alertas en tiempo real provenientes del dispatcher.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant={pushEnabled ? "outline" : "secondary"}
                      className="rounded-full px-3 py-1 text-xs font-medium"
                    >
                      {pushEnabled
                        ? "Suscripción activa"
                        : pushLoading
                        ? "Sincronizando..."
                        : "Suscripción inactiva"}
                    </Badge>
                    {pushPermission !== "unsupported" && pushPermission !== "granted" && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => void requestPushPermission()}
                        disabled={pushLoading}
                        className="flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <BellRing className="h-4 w-4" aria-hidden="true" />
                        Activar notificaciones
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void sendTestNotification()}
                      disabled={!pushEnabled || pushTesting}
                      className="flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    >
                      <Radio className="h-4 w-4" aria-hidden="true" />
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
                            className="flex items-start justify-between gap-3 rounded-xl border border-border/50 bg-[hsl(var(--surface-muted))] p-3"
                          >
                            <div className="space-y-1">
                              <p className="text-sm font-medium text-card-foreground">{event.title}</p>
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
                              className="-mr-1 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                              onClick={() => dismissPushEvent(event.id)}
                            >
                              Cerrar
                            </Button>
                          </div>
                        ))
                    )}
                  </div>
                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Registro de eventos
                    </p>
                    <ScrollArea
                      className="h-32 rounded-xl border border-border/40 bg-[hsl(var(--surface))] p-2"
                      aria-label="Registro de eventos de notificaciones push"
                    >
                      {pushLogs.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          Esperando eventos auditables del dispatcher...
                        </p>
                      ) : (
                        <ul className="space-y-1 text-xs text-card-foreground">
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
            </motion.div>
            <motion.div className="h-full" {...createCardMotion(0.16)}>
              <Card className="surface-card h-full">
                <CardHeader className="space-y-1 pb-4">
                  <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
                    <Activity className="h-5 w-5 text-primary" aria-hidden="true" /> Estado de la sesión
                  </CardTitle>
                  <CardDescription>
                    Mantén el pulso de la conexión en vivo y los últimos eventos del mercado.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm" aria-live="polite">
                  <div className="flex items-center gap-2 text-xs font-medium" aria-atomic="true">
                    <span className={realtimeConnected ? "text-success" : "text-destructive"}>
                      {realtimeConnected ? "Conectado a Realtime" : "Conexión inactiva"}
                    </span>
                    {realtimeHighlight && (
                      <span className="text-muted-foreground">•</span>
                    )}
                    {realtimeHighlight && (
                      <span className="text-card-foreground">{realtimeHighlight}</span>
                    )}
                  </div>
                  {realtimeData && (
                    <pre
                      className="max-h-40 overflow-auto rounded-xl border border-border/50 bg-[hsl(var(--surface))] p-3 text-xs text-muted-foreground"
                      aria-label="Detalle del último evento en tiempo real"
                    >
                      {JSON.stringify(realtimeData, null, 2)}
                    </pre>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          </section>
        </div>
        <section
          className="grid flex-1 gap-4 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]"
          data-testid="dashboard-modules"
        >
          <div className="grid auto-rows-min gap-4">
            <motion.div className="h-full" {...createCardMotion(0.08)}>
              <PortfolioPanel token={token ?? undefined} />
            </motion.div>
            {/* [Codex] nuevo - tarjeta de indicadores con insights AI */}
            <motion.div className="h-full" {...createCardMotion(0.12)}>
              <Card className="surface-card flex flex-col" data-testid="dashboard-indicators">
                <CardHeader className="flex flex-wrap items-center justify-between gap-3 pb-4">
                  <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
                    <SignalHigh className="h-5 w-5 text-primary" aria-hidden="true" /> Indicadores clave ({indicatorSymbol})
                  </CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleRefreshIndicators}
                    disabled={indicatorLoading || historicalLoading || historicalValidating}
                    className="flex items-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    aria-live="polite"
                  >
                    <LineChart className="h-4 w-4" aria-hidden="true" />
                    {indicatorLoading || historicalLoading || historicalValidating
                      ? "Actualizando..."
                      : "Actualizar"}
                  </Button>
                </CardHeader>
                <CardContent
                  className="pt-0"
                  aria-busy={indicatorLoading || historicalLoading || historicalValidating}
                  aria-live="polite"
                >
                  {indicatorError && (
                    <p className="text-sm text-destructive" role="status">
                      {indicatorError}
                    </p>
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
            </motion.div>
            <motion.div className="h-full" {...createCardMotion(0.16)}>
              <Card className="surface-card flex flex-col" data-testid="dashboard-chat">
                <CardHeader className="pb-4">
                  <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
                    <Bot className="h-5 w-5 text-primary" aria-hidden="true" /> Asistente estratégico
                  </CardTitle>
                  <CardDescription>
                    Conversa con el bot para contextualizar las señales del mercado.
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex h-full flex-col gap-4" aria-live="polite">
                  <Suspense
                    fallback={
                      <PanelSkeleton
                        lines={5}
                        aria-label="Cargando conversación con el asistente estratégico"
                      />
                    }
                  >
                    <ChatPanel token={token ?? undefined} />
                  </Suspense>
                </CardContent>
              </Card>
            </motion.div>
          </div>
          <div className="grid auto-rows-min gap-4">
            <motion.div className="h-full" {...createCardMotion(0.08)}>
              <Suspense
                fallback={
                  <AsyncModuleFallback
                    title="Alertas"
                    description="Sincronizando tus alertas personalizadas..."
                    icon={<BellRing className="h-5 w-5 text-primary" aria-hidden="true" />}
                    aria-label="Sección de alertas cargándose"
                    className="h-full"
                  />
                }
              >
                <AlertsPanel token={token ?? undefined} />
              </Suspense>
            </motion.div>
            <motion.div className="h-full" {...createCardMotion(0.12)}>
              <NewsPanel token={token ?? undefined} />
            </motion.div>
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
