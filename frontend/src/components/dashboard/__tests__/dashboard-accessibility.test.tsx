import type { ReactNode } from "react";

import { render, screen, within } from "@testing-library/react";
import { axe } from "jest-axe";

jest.mock("@/components/providers/auth-provider", () => ({
  useAuth: () => ({
    user: { id: "1", email: "user@example.com", name: "Jane" },
    loading: false,
    token: "token",
    logout: jest.fn(),
  }),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ replace: jest.fn() }),
}));

jest.mock("@/components/sidebar/market-sidebar", () => ({
  MarketSidebar: () => (
    <div>
      <h2>BullBearBroker</h2>
      <button>Cerrar sesión</button>
    </div>
  ),
}));

jest.mock("@/components/news/news-panel", () => ({
  NewsPanel: () => <section>news</section>,
}));

jest.mock("@/components/alerts/alerts-panel", () => ({
  AlertsPanel: () => <section>alerts</section>,
}));

jest.mock("@/components/chat/chat-panel", () => ({
  ChatPanel: () => <div>chat</div>,
}));

jest.mock("@/components/indicators/IndicatorsChart", () => ({
  IndicatorsChart: () => <div>chart</div>,
}));

jest.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
}));

jest.mock("@/lib/api", () => ({
  getIndicators: jest.fn(async () => ({
    symbol: "BTCUSDT",
    interval: "1h",
    indicators: {},
    series: {},
  })),
  sendChatMessage: jest.fn(async () => ({
    messages: [{ role: "assistant", content: "ok" }],
  })),
}));

import { DashboardPage } from "../dashboard-page";

describe("DashboardPage accesibilidad", () => {
  it("no tiene violaciones básicas", async () => {
    const originalConsoleError = console.error;
    const consoleErrorSpy = jest
      .spyOn(console, "error")
      .mockImplementation((...args) => {
        if (
          typeof args[0] === "string" &&
          args[0].includes("not wrapped in act")
        ) {
          return;
        }
        originalConsoleError(...(args as Parameters<typeof console.error>));
      });

    try {
      const utils = render(<DashboardPage />);
      const sidebarHeading = await screen.findByText(/BullBearBroker/i);
      await within(sidebarHeading.parentElement as HTMLElement).findByRole(
        "button",
        { name: /Cerrar sesión/i },
      );
      const { container } = utils;
      expect(await axe(container)).toHaveNoViolations();
    } finally {
      consoleErrorSpy.mockRestore();
    }
  }, 30000);
});
