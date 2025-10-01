import React from "react";
import { act, customRender, screen, waitFor } from "@/tests/utils/renderWithProviders";
import userEvent from "@testing-library/user-event";

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

const mockUsePushNotifications = jest.fn(() => ({
  enabled: false,
  error: null,
  permission: "default" as NotificationPermission,
  loading: false,
}));

jest.mock("@/components/sidebar/market-sidebar", () => ({
  MarketSidebar: (props: any) => mockMarketSidebar(props),
}));

jest.mock("@/components/alerts/alerts-panel", () => ({
  AlertsPanel: (props: any) => mockAlertsPanel(props),
}));

jest.mock("@/components/news/news-panel", () => ({
  NewsPanel: (props: any) => mockNewsPanel(props),
}));

jest.mock("@/components/chat/chat-panel", () => ({
  ChatPanel: (props: any) => mockChatPanel(props),
}));

jest.mock("@/components/portfolio/PortfolioPanel", () => ({
  PortfolioPanel: (props: any) => mockPortfolioPanel(props),
}));

jest.mock("@/components/indicators/IndicatorsChart", () => ({
  IndicatorsChart: (props: any) => mockIndicatorsChart(props),
}));

jest.mock("@/components/dashboard/theme-toggle", () => ({
  ThemeToggle: () => <button type="button">Tema</button>,
}));

jest.mock("@/hooks/usePushNotifications", () => ({
  usePushNotifications: (token: string | undefined) => mockUsePushNotifications(token),
}));

jest.mock("@/hooks/useHistoricalData", () => ({
  useHistoricalData: (symbol: string, options: any) => mockUseHistoricalData(symbol, options),
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
    mockUsePushNotifications.mockImplementation(() => ({
      enabled: false,
      error: null,
      permission: "default" as NotificationPermission,
      loading: false,
    }));
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
    expect(screen.getByText(/Ana/i)).toBeInTheDocument();
    expect(mockMarketSidebar).toHaveBeenCalled();
    expect(mockPortfolioPanel).toHaveBeenCalledWith(
      expect.objectContaining({ token: baseAuth.token })
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
      expect(mockIndicatorsChart).toHaveBeenCalledWith(
        expect.objectContaining({
          symbol: "BTCUSDT",
          interval: "1h",
          indicators: expect.any(Object),
          history: expect.objectContaining({ symbol: "BTCUSDT" }),
        })
      );
    });

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
      })
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
    mockUsePushNotifications.mockReturnValue({
      enabled: true,
      error: null,
      permission: "granted",
      loading: false,
    });
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
    const cards = Array.from(
      content.querySelectorAll('[data-testid^="dashboard-"]')
    ).map((node) => node.getAttribute("data-testid"));

    const summary = {
      shellClass: shell.className,
      contentClass: content.className,
      modulesClass: modules.className,
      cards,
      hasSidebar: mockMarketSidebar.mock.calls.length > 0,
      pushStatus: screen.getByText(/Push inactivo/i).textContent,
    };

    expect(summary).toMatchInlineSnapshot(`
{
  "cards": [
    "dashboard-modules",
    "dashboard-indicators",
    "dashboard-chat",
  ],
  "contentClass": "flex flex-col gap-6 p-4 lg:p-6",
  "hasSidebar": true,
  "modulesClass": "grid flex-1 gap-6 lg:grid-cols-2 xl:grid-cols-[2fr_1fr]",
  "pushStatus": "Push inactivo",
  "shellClass": "grid min-h-screen bg-background text-foreground md:grid-cols-[280px_1fr]",
}
`);
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

      expect(
        await screen.findByText("Aún no se han cargado indicadores.")
      ).toBeInTheDocument();
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
    mockUsePushNotifications.mockReturnValue({
      enabled: false,
      error: "No se pudo registrar push",
      permission: "denied",
      loading: false,
    });
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

    expect(await screen.findByText("No se pudo registrar push")).toBeInTheDocument();
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
