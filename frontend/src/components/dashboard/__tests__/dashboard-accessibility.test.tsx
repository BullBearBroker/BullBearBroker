import { act, render, screen } from "@testing-library/react";
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
    <aside>
      <h2>BullBearBroker</h2>
    </aside>
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
    let utils: ReturnType<typeof render> | undefined;

    await act(async () => {
      utils = render(<DashboardPage />);
      await screen.findByRole("heading", { name: /BullBearBroker/i });
    });

    const { container } = utils!;
    expect(await axe(container)).toHaveNoViolations();
  });
});
