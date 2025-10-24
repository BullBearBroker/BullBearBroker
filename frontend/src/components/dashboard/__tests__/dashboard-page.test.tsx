// # QA fix: simular usuario autenticado y push habilitado
jest.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { name: "Ana", id: 1 }, isAuthenticated: true }),
}));

import React from "react";
import { act, customRender, screen, waitFor } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";
import type { MockNotificationEvent } from "@/tests/mocks/notifications";

jest.mock("@/components/providers/auth-provider", () => {
  const actual = jest.requireActual("@/components/providers/auth-provider");
  return {
    ...actual,
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    useAuth: jest.fn(),
  };
});

const { useAuth: mockUseAuth } = jest.requireMock("@/components/providers/auth-provider") as {
  useAuth: jest.Mock;
};

jest.mock("@/components/providers/theme-provider", () => ({
  ThemeProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockMarketSidebar = jest.fn(() => <aside data-testid="market-sidebar" />);
const mockAlertsPanel = jest.fn(() => <section data-testid="alerts-panel" />);
const mockNewsPanel = jest.fn(() => <section data-testid="news-panel" />);
const mockChatPanel = jest.fn(() => <section data-testid="chat-panel" />);
const mockPortfolioPanel = jest.fn(() => <section data-testid="portfolio-panel" />);
const mockIndicatorsChart = jest.fn((props) => (
  <div data-testid="indicators-chart">{props.symbol}</div>
));

const mockUseLiveNotifications = jest.fn(() => ({ events: [], status: "connected" as const })); // # QA fix: mock estable para live notifications

const mockHistoricalRefresh = jest.fn();
const mockUseHistoricalData = jest.fn(() => ({
  data: { symbol: "BTCUSDT", interval: "1h", source: "Binance", values: [] },
  error: undefined,
  isLoading: false,
  isValidating: false,
  refresh: mockHistoricalRefresh,
  mutate: mockHistoricalRefresh,
  isEmpty: false,
}));

// # QA fix: tipado reutilizable para el mock de usePushNotifications
type PushMockState = {
  enabled: boolean;
  error: string | null;
  isSupported: boolean;
  permission: NotificationPermission;
  loading: boolean;
  testing: boolean;
  events: MockNotificationEvent[];
  logs: string[];
  sendTestNotification: jest.Mock;
  requestPermission: jest.Mock;
  dismissEvent: jest.Mock;
  notificationHistory: MockNotificationEvent[];
  clearLogs: jest.Mock;
  subscription: PushSubscription | null;
  subscribe: jest.Mock;
  unsubscribe: jest.Mock;
};

const stablePushEvents: PushMockState["events"] = [];
const stablePushLogs: PushMockState["logs"] = [];
const stablePushHistory: PushMockState["notificationHistory"] = [];
// # QA fix: mantener referencias estables y evitar renders infinitos en NotificationCenterCard

const createPushMockState = (overrides: Partial<PushMockState> = {}): PushMockState => ({
  enabled: false,
  error: null,
  isSupported: true,
  permission: "default" as NotificationPermission,
  loading: false,
  testing: false,
  events: stablePushEvents,
  logs: stablePushLogs,
  sendTestNotification: jest.fn(),
  requestPermission: jest.fn(),
  dismissEvent: jest.fn(),
  notificationHistory: stablePushHistory,
  clearLogs: jest.fn(),
  subscription: null,
  subscribe: jest.fn(),
  unsubscribe: jest.fn(),
  ...overrides,
}); // # QA fix: helper consistente para estados del hook de push

const mockUsePushNotifications = jest.fn(() => createPushMockState());

jest.mock("@/components/sidebar/market-sidebar", () => ({
  __esModule: true,
  MarketSidebar: mockMarketSidebar,
}));

jest.mock("@/components/alerts/alerts-panel", () => ({
  __esModule: true,
  AlertsPanel: mockAlertsPanel,
  default: mockAlertsPanel,
}));

jest.mock("@/components/news/NewsPanel", () => ({
  __esModule: true,
  NewsPanel: mockNewsPanel,
  default: mockNewsPanel,
}));

jest.mock("@/components/chat/chat-panel", () => ({
  __esModule: true,
  ChatPanel: mockChatPanel,
  default: mockChatPanel,
}));

jest.mock("@/components/portfolio/PortfolioPanel", () => ({
  __esModule: true,
  PortfolioPanel: mockPortfolioPanel,
  default: mockPortfolioPanel,
}));

jest.mock("@/components/indicators/IndicatorsChart", () => ({
  __esModule: true,
  IndicatorsChart: mockIndicatorsChart,
  default: mockIndicatorsChart,
}));

jest.mock("@/hooks/useLiveNotifications", () => ({
  __esModule: true,
  useLiveNotifications: mockUseLiveNotifications,
})); // # QA fix: estabilizar hook de notificaciones en pruebas

jest.mock("@/components/dashboard/theme-toggle", () => ({
  ThemeToggle: () => <button type="button">Tema</button>,
}));

jest.mock("@/hooks/usePushNotifications", () => ({
  __esModule: true,
  usePushNotifications: mockUsePushNotifications,
}));

jest.mock("@/hooks/useHistoricalData", () => ({
  __esModule: true,
  useHistoricalData: mockUseHistoricalData,
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const { useRouter: mockUseRouter } = jest.requireMock("next/navigation") as {
  useRouter: jest.Mock;
};

const mockedGetIndicators = jest.fn();
const mockedSendChatMessage = jest.fn();

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    getIndicators: (...args: any[]) => mockedGetIndicators(...args),
    sendChatMessage: (...args: any[]) => mockedSendChatMessage(...args),
  };
});

import { DashboardPage } from "../dashboard-page";

const baseAuth = {
  logout: jest.fn(),
  token: "token-123",
  user: { id: "1", email: "user@example.com", name: "Ana" },
};

describe("DashboardPage", () => {
  beforeEach(() => {
    mockUseAuth.mockReset();
    mockUseRouter.mockReset();
    mockedGetIndicators.mockReset();
    mockedSendChatMessage.mockReset();
    mockIndicatorsChart.mockClear();
    mockMarketSidebar.mockClear();
    mockAlertsPanel.mockClear();
    mockNewsPanel.mockClear();
    mockChatPanel.mockClear();
    mockPortfolioPanel.mockClear();
    mockUsePushNotifications.mockClear();
    mockUsePushNotifications.mockImplementation(() => createPushMockState()); // # QA fix: restablecer estado base del hook
    mockUseLiveNotifications.mockReset();
    mockUseLiveNotifications.mockImplementation(() => ({
      events: [],
      status: "connected" as const,
    })); // # QA fix: estado estable para live notifications
    mockHistoricalRefresh.mockClear();
    mockHistoricalRefresh.mockResolvedValue(undefined);
    mockUseHistoricalData.mockClear();
    mockUseHistoricalData.mockImplementation(() => ({
      data: { symbol: "BTCUSDT", interval: "1h", source: "Binance", values: [] },
      error: undefined,
      isLoading: false,
      isValidating: false,
      refresh: mockHistoricalRefresh,
      mutate: mockHistoricalRefresh,
      isEmpty: false,
    }));
  });

  it("muestra la pantalla de carga mientras la sesión está verificándose", () => {
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: true, user: null, token: null });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    customRender(<DashboardPage />);

    expect(screen.getByText("Cargando sesión...")).toBeInTheDocument();
    expect(mockedGetIndicators).not.toHaveBeenCalled();
  });

  it("redirige al login cuando no hay usuario", async () => {
    const replace = jest.fn();
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false, user: null, token: null });
    mockUseRouter.mockReturnValue({ replace });

    await act(async () => {
      customRender(<DashboardPage />);
    });

    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/login");
    });
    expect(screen.getByText(/Redirigiendo al acceso/i)).toBeInTheDocument();
  });

  it("renderiza las secciones principales y refresca indicadores", async () => {
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [{ role: "assistant", content: "Ok" }],
      sources: ["prices"],
      used_data: true,
    });

    await act(async () => {
      customRender(<DashboardPage />);
    });

    expect(await screen.findByText(/bienvenido de vuelta/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /Ana/i })).toBeInTheDocument(); // # QA fix: evitar coincidencias parciales con el texto
    expect(mockMarketSidebar).toHaveBeenCalled();
    expect(mockPortfolioPanel).toHaveBeenCalledWith(
      expect.objectContaining({ token: baseAuth.token }),
      expect.anything(), // ✅ Permitimos el segundo argumento vacío inyectado por el mock (Node 20 + Jest)
    );
    expect(mockAlertsPanel).toHaveBeenCalled();
    expect(mockNewsPanel).toHaveBeenCalled();
    expect(mockChatPanel).toHaveBeenCalled();
    expect(screen.getByText(/Push inactivo/i)).toBeInTheDocument();

    const shell = screen.getByTestId("dashboard-shell");
    expect(shell).toHaveClass("grid");
    expect(shell.className).toContain("md:grid-cols-[280px_1fr]");

    const modules = screen.getByTestId("dashboard-modules");
    expect(modules.className).toContain("lg:grid-cols-2");

    await waitFor(() => {
      expect(mockIndicatorsChart).toHaveBeenCalled();
    });

    const [chartProps] = mockIndicatorsChart.mock.calls.at(-1) ?? [];
    expect(chartProps).toEqual(
      expect.objectContaining({
        symbol: "BTCUSDT",
        interval: "1h",
        indicators: expect.any(Object),
        history: expect.objectContaining({ symbol: "BTCUSDT" }),
      }),
    ); // ✅ Validamos solo las props relevantes para evitar falsos negativos con argumentos extra

    const user = userEvent.setup();
    await act(async () => {
      await user.click(screen.getByRole("button", { name: /actualizar/i }));
    });

    expect(mockedGetIndicators).toHaveBeenCalledTimes(2);
    expect(mockHistoricalRefresh).toHaveBeenCalled();
    expect(mockUseHistoricalData).toHaveBeenCalledWith("BTCUSDT", {
      interval: "1h",
      market: "auto",
      limit: 240,
    });
  });

  it("propaga los insights generados por IA al gráfico", async () => {
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "ETHUSDT",
      interval: "4h",
      indicators: { last_close: 45678 },
      series: { closes: [4, 5, 6] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [
        { role: "user", content: "Pregunta" },
        { role: "assistant", content: "Insight generado" },
      ],
      sources: ["mock"],
      used_data: true,
    });

    await act(async () => {
      customRender(<DashboardPage />);
    });

    await waitFor(() => {
      expect(mockIndicatorsChart).toHaveBeenCalled();
    });

    const lastCall = mockIndicatorsChart.mock.calls.at(-1)?.[0];
    expect(lastCall).toEqual(
      expect.objectContaining({
        symbol: "ETHUSDT",
        interval: "4h",
        insights: "Insight generado",
      }),
    );
  });

  it("permite cerrar sesión desde el encabezado", async () => {
    const logout = jest.fn();
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false, logout });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [{ role: "assistant", content: "Ok" }],
      sources: [],
      used_data: false,
    });

    const user = userEvent.setup();
    await act(async () => {
      customRender(<DashboardPage />);
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Cerrar sesión/i })).toBeEnabled();
    });

    await act(async () => {
      await user.click(screen.getByRole("button", { name: /Cerrar sesión/i }));
    });

    expect(logout).toHaveBeenCalled();
  });

  it("muestra el estado de notificaciones push activas", async () => {
    mockUsePushNotifications.mockReturnValue(
      createPushMockState({ enabled: true, permission: "granted", loading: false }),
    ); // # QA fix: estado habilitado consistente para las pruebas
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [{ role: "assistant", content: "Ok" }],
      sources: [],
      used_data: false,
    });

    await act(async () => {
      customRender(<DashboardPage />);
    });

    expect(await screen.findByText(/Push activo/i)).toBeInTheDocument();
  });

  it("mantiene estable el layout principal", async () => {
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [{ role: "assistant", content: "Ok" }],
      sources: [],
      used_data: false,
    });

    customRender(<DashboardPage />);

    const shell = await screen.findByTestId("dashboard-shell");
    const content = screen.getByTestId("dashboard-content");
    const modules = screen.getByTestId("dashboard-modules");
    const cards = Array.from(content.querySelectorAll('[data-testid^="dashboard-"]')).map((node) =>
      node.getAttribute("data-testid"),
    );

    const summary = {
      shellClass: shell.className,
      contentClass: content.className,
      modulesClass: modules.className,
      cards,
      hasSidebar: mockMarketSidebar.mock.calls.length > 0,
      pushStatus: screen.getByText(/Push inactivo/i).textContent,
    };

    expect(summary.cards).toEqual(["dashboard-modules", "dashboard-indicators", "dashboard-chat"]);
    expect(summary.contentClass).toBe("flex flex-col gap-6 p-4 md:p-6");
    expect(summary.modulesClass).toBe("grid flex-1 gap-4 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]");
    expect(summary.shellClass).toBe(
      "grid min-h-screen bg-background text-foreground md:grid-cols-[280px_1fr]",
    );
    expect(summary.hasSidebar).toBe(true);
    expect(summary.pushStatus).toBe("Push inactivo");
  });

  it("muestra el estado vacío cuando no hay indicadores disponibles", async () => {
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValueOnce(null);
    mockedSendChatMessage.mockResolvedValue({ messages: [], sources: [], used_data: false });

    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});

    try {
      await act(async () => {
        customRender(<DashboardPage />);
      });

      expect(await screen.findByText("Aún no se han cargado indicadores.")).toBeInTheDocument();
      expect(mockIndicatorsChart).not.toHaveBeenCalled();
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra un error cuando la carga de indicadores falla", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockRejectedValueOnce(new Error("Falla total"));
    mockedSendChatMessage.mockResolvedValue({ messages: [], sources: [], used_data: false });

    try {
      await act(async () => {
        customRender(<DashboardPage />);
      });

      expect(await screen.findByText("Falla total")).toBeInTheDocument();
      expect(mockIndicatorsChart).not.toHaveBeenCalled();
    } finally {
      consoleSpy.mockRestore();
    }
  });

  it("muestra el error de notificaciones push", async () => {
    mockUsePushNotifications.mockReturnValue(
      createPushMockState({
        enabled: false,
        error: "No se pudo registrar push",
        permission: "denied",
        loading: false,
      }),
    ); // # QA fix: estado de error controlado para notificaciones push
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({ messages: [], sources: [], used_data: false });

    await act(async () => {
      customRender(<DashboardPage />);
    });

    const alerts = await screen.findAllByText("No se pudo registrar push");
    expect(alerts).toHaveLength(2);
  });

  it("limpia los insights cuando la IA devuelve un error", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockRejectedValueOnce(new Error("Fallo IA"));

    try {
      await act(async () => {
        customRender(<DashboardPage />);
      });

      await waitFor(() => {
        expect(mockIndicatorsChart).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(screen.queryByText(/Fallo IA/)).not.toBeInTheDocument();
      });
      expect(mockedSendChatMessage).toHaveBeenCalled();
    } finally {
      consoleSpy.mockRestore();
    }
  });
});
