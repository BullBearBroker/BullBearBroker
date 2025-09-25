import { render, screen } from "@testing-library/react";
import useSWR from "swr";

import { MarketSidebar } from "../market-sidebar";

jest.mock("swr", () => ({
  __esModule: true,
  default: jest.fn()
}));

const useSWRMock = useSWR as unknown as jest.Mock;

describe("MarketSidebar", () => {
  const user = { id: 1, email: "user@example.com" } as const;
  const onLogout = jest.fn();

  beforeEach(() => {
    onLogout.mockReset();
    useSWRMock.mockImplementation((key: unknown[]) => {
      const [, type] = key as [string, "crypto" | "stocks" | "forex", string | undefined];
      const mockData = {
        crypto: [
          { symbol: "BTC", price: 50000, change_24h: 2.5 },
          { symbol: "ETH", price: 3000, change_24h: -1.2 }
        ],
        stocks: [{ symbol: "AAPL", price: 180.5, change_24h: 1.1 }],
        forex: [{ symbol: "EUR/USD", price: 1.08, change_24h: 0.2 }]
      } satisfies Record<"crypto" | "stocks" | "forex", unknown>;

      return {
        data: mockData[type],
        error: undefined,
        isLoading: false
      };
    });
  });

  afterEach(() => {
    useSWRMock.mockReset();
  });

  it("muestra los datos de los mercados", () => {
    render(<MarketSidebar token="token" user={user} onLogout={onLogout} />);

    expect(screen.getByText(/bullbearbroker/i)).toBeInTheDocument();
    expect(screen.getByText(user.email)).toBeInTheDocument();
    expect(screen.getByText("BTC")).toBeInTheDocument();
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/eur\/usd/i)).toBeInTheDocument();
  });
});
