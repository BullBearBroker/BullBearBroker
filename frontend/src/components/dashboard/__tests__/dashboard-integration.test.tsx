import React from "react";
import { act, customRender, screen, waitFor, within } from "@/tests/utils/renderWithProviders";
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

jest.mock("@/hooks/useAlertsWebSocket", () => ({
  __esModule: true,
  useAlertsWebSocket: jest.fn(() => ({
    status: "closed",
    lastMessage: null,
    error: null,
    reconnect: jest.fn(),
    disconnect: jest.fn(),
  })),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

const { useRouter: mockUseRouter } = jest.requireMock("next/navigation") as {
  useRouter: jest.Mock;
};

const mockedGetIndicators = jest.fn();
const mockedSendChatMessage = jest.fn();
const mockedListPortfolio = jest.fn();
const mockedCreatePortfolioItem = jest.fn();
const mockedDeletePortfolioItem = jest.fn();
const mockedListAlerts = jest.fn();
const mockedCreateAlert = jest.fn();
const mockedUpdateAlert = jest.fn();
const mockedDeleteAlert = jest.fn();
const mockedSendAlertNotification = jest.fn();
const mockedSuggestAlertCondition = jest.fn();
const mockedListNews = jest.fn();
const mockedGetMarketQuote = jest.fn();

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    getIndicators: (...args: any[]) => mockedGetIndicators(...args),
    sendChatMessage: (...args: any[]) => mockedSendChatMessage(...args),
    listPortfolio: (...args: any[]) => mockedListPortfolio(...args),
    createPortfolioItem: (...args: any[]) => mockedCreatePortfolioItem(...args),
    deletePortfolioItem: (...args: any[]) => mockedDeletePortfolioItem(...args),
    listAlerts: (...args: any[]) => mockedListAlerts(...args),
    createAlert: (...args: any[]) => mockedCreateAlert(...args),
    updateAlert: (...args: any[]) => mockedUpdateAlert(...args),
    deleteAlert: (...args: any[]) => mockedDeleteAlert(...args),
    sendAlertNotification: (...args: any[]) => mockedSendAlertNotification(...args),
    suggestAlertCondition: (...args: any[]) => mockedSuggestAlertCondition(...args),
    listNews: (...args: any[]) => mockedListNews(...args),
    getMarketQuote: (...args: any[]) => mockedGetMarketQuote(...args),
  };
});

import { DashboardPage } from "../dashboard-page";

const baseAuth = {
  logout: jest.fn(),
  token: "token-123",
  user: { id: "1", email: "user@example.com", name: "Ana" },
};

const portfolioFixture = {
  total_value: 12500,
  items: [
    {
      id: "1",
      symbol: "BTCUSDT",
      amount: 0.5,
      price: 25000,
      value: 12500,
    },
  ],
};

const alertsFixture = [
  {
    id: "1",
    title: "BTC arriba",
    asset: "BTC",
    condition: "> 30000",
    value: 30000,
    active: true,
  },
];

const newsFixture = [
  {
    id: "1",
    title: "Mercados en alza",
    url: "https://example.com/news",
    summary: "Resumen de mercado",
    source: "Reuters",
    published_at: new Date("2024-01-15T10:00:00Z").toISOString(),
  },
];

describe("DashboardPage integration", () => {
  beforeAll(() => {
    class ResizeObserverMock implements ResizeObserver {
      callback: ResizeObserverCallback;

      constructor(callback: ResizeObserverCallback) {
        this.callback = callback;
      }

      observe(): void {}

      unobserve(): void {}

      disconnect(): void {}

      takeRecords(): ResizeObserverEntry[] {
        return [];
      }
    }

    Object.defineProperty(globalThis, "ResizeObserver", {
      configurable: true,
      writable: true,
      value: ResizeObserverMock,
    });
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseAuth.mockReturnValue({ ...baseAuth, loading: false });
    mockUseRouter.mockReturnValue({ replace: jest.fn() });

    mockedGetIndicators.mockResolvedValue({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { last_close: 12345 },
      series: { closes: [1, 2, 3] },
    });
    mockedSendChatMessage.mockResolvedValue({
      messages: [{ role: "assistant", content: "Análisis" }],
      sources: ["indicators"],
      used_data: true,
    });
    mockedListPortfolio.mockResolvedValue(portfolioFixture);
    mockedCreatePortfolioItem.mockResolvedValue({ id: "2" });
    mockedDeletePortfolioItem.mockResolvedValue(undefined);
    mockedListAlerts.mockResolvedValue(alertsFixture);
    mockedCreateAlert.mockResolvedValue({ id: "2" });
    mockedUpdateAlert.mockResolvedValue(undefined);
    mockedDeleteAlert.mockResolvedValue(undefined);
    mockedSendAlertNotification.mockResolvedValue({ ok: true });
    mockedSuggestAlertCondition.mockResolvedValue({
      suggestion: "BTC > 32000",
      notes: "Basado en momentum",
    });
    mockedListNews.mockResolvedValue(newsFixture);
    mockedGetMarketQuote.mockImplementation(async (type: string, symbol: string) => ({
      symbol,
      price: type === "forex" ? 1.08 : 30000,
      raw_change: 1.25,
      source: "Demo",
      type,
    }));
  });

  it("renders all dashboard modules and keeps portfolio actions accessible", async () => {
    await act(async () => {
      customRender(<DashboardPage />);
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /portafolio/i })).toBeInTheDocument();
    });

    expect(
      screen.getByRole("heading", { name: /indicadores clave \(BTCUSDT\)/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /chat con ia/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /alertas personalizadas/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /noticias/i })).toBeInTheDocument();

    const portfolioLink = screen.getByRole("link", { name: /ver portafolio/i });
    expect(portfolioLink).toHaveAttribute("href", "/portfolio");

    expect(await screen.findByRole("button", { name: /eliminar btcusdt/i })).toBeInTheDocument();
    expect(screen.getByText(/Total:/i)).toBeInTheDocument();

    const portfolioCard = screen.getByRole("heading", { name: /portafolio/i }).closest("div")!
      .parentElement!.parentElement! as HTMLElement;

    const symbolInput = within(portfolioCard).getByPlaceholderText(/BTCUSDT, AAPL, EURUSD/i);
    const amountInput = within(portfolioCard).getByPlaceholderText(/cantidad/i);

    const user = userEvent.setup();

    await act(async () => {
      await user.type(symbolInput, "eth");
      await user.type(amountInput, "2");
      await user.click(screen.getByRole("button", { name: /agregar activo/i }));
    });

    await waitFor(() => {
      expect(mockedCreatePortfolioItem).toHaveBeenCalledWith(
        baseAuth.token,
        expect.objectContaining({ symbol: "ETH", amount: 2 }),
      );
    });

    expect(mockedGetIndicators).toHaveBeenCalled();
  });
});
