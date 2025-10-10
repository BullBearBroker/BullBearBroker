import { render, screen, waitFor } from "@testing-library/react";

import { DashboardPage } from "@/components/dashboard/dashboard-page";
import { server } from "@/tests/msw/server";
import { makeMarketQuoteHandler } from "@/tests/msw/handlers";

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/components/alerts/alerts-panel", () => ({
  AlertsPanel: () => <div data-testid="alerts-panel" />,
}));

jest.mock("@/components/chat/chat-panel", () => ({
  ChatPanel: () => <div data-testid="chat-panel" />,
}));

jest.mock("@/components/indicators/IndicatorsChart", () => ({
  __esModule: true,
  IndicatorsChart: () => <div data-testid="indicators-chart" />,
  default: () => <div data-testid="indicators-chart" />,
}));

jest.mock("@/components/dashboard/theme-toggle", () => ({
  ThemeToggle: () => <button type="button">Modo</button>,
}));

jest.mock("@/lib/api", () => {
  const actual = jest.requireActual("@/lib/api");
  return {
    ...actual,
    getIndicators: jest.fn(async () => ({
      symbol: "BTCUSDT",
      interval: "1h",
      indicators: { rsi: 50 },
      series: {},
    })),
    sendChatMessage: jest.fn(async (messages: any[]) => ({
      messages: [...messages, { role: "assistant", content: "Análisis listo" }],
    })),
  };
});

import { useAuth } from "@/components/providers/auth-provider";
import { useRouter } from "next/navigation";

const mockedUseAuth = useAuth as unknown as jest.Mock;
const mockedUseRouter = useRouter as unknown as jest.Mock;

describe("Flujo de autenticación e inicio", () => {
  afterEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  it("redirige al login cuando no hay usuario", async () => {
    const replace = jest.fn();
    mockedUseRouter.mockReturnValue({ replace });
    mockedUseAuth.mockReturnValue({ user: null, loading: false, token: null, logout: jest.fn() });

    render(<DashboardPage />);

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(screen.getByText(/redirigiendo al acceso/i)).toBeInTheDocument();
  });

  it("muestra dashboard con datos cuando hay sesión", async () => {
    mockedUseRouter.mockReturnValue({ replace: jest.fn() });
    mockedUseAuth.mockReturnValue({
      user: { id: "1", email: "user@example.com", name: "Jane" },
      loading: false,
      token: "token",
      logout: jest.fn(),
    });

    server.use(
      makeMarketQuoteHandler("crypto", { price: 50_000 }),
      makeMarketQuoteHandler("stocks", { price: 180.5 }),
      makeMarketQuoteHandler("forex", { price: 1.08 }),
    );

    render(<DashboardPage />);

    expect(await screen.findByText(/jane/i)).toBeInTheDocument();
    expect(await screen.findByText("BTCUSDT")).toBeInTheDocument();
    expect(await screen.findByText(/mercados al alza/i)).toBeInTheDocument();
    expect(screen.getByTestId("alerts-panel")).toBeInTheDocument();
    expect(screen.getByTestId("chat-panel")).toBeInTheDocument();
  });
});
