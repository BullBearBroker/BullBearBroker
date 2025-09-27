// [Codex] nuevo - Ajustes de textos reales y estados de SWR
import { act, render, screen, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { MarketSidebar } from "../market-sidebar";
import {
  makeMarketEmptyHandler,
  makeMarketErrorHandler,
  makeMarketQuoteHandler,
} from "@/tests/msw/handlers";
import { server } from "@/tests/msw/server";

const user = { id: 1, email: "user@example.com" } as const;
const onLogout = jest.fn();

const renderSidebar = () =>
  render(
    <SWRConfig
      value={{
        provider: () => new Map(),
        dedupingInterval: 0,
        focusThrottleInterval: 0,
        revalidateOnFocus: false,
      }}
    >
      <MarketSidebar token="token" user={user} onLogout={onLogout} />
    </SWRConfig>
  );

describe("MarketSidebar", () => {
  beforeEach(() => {
    onLogout.mockReset();
  });

  it("muestra los datos de los mercados", async () => {
    renderSidebar();

    expect(screen.getByText(/bullbearbroker/i)).toBeInTheDocument();
    expect(screen.getByText(user.email)).toBeInTheDocument();
    expect(await screen.findByText("BTCUSDT")).toBeInTheDocument();
    expect(await screen.findByText("AAPL")).toBeInTheDocument();
    expect(await screen.findByText(/eur\/usd/i)).toBeInTheDocument();
    await waitFor(() => {
      const initialPrice = screen
        .getByText("BTCUSDT")
        .parentElement?.parentElement?.querySelector("div.text-right > p");
      expect(initialPrice).toHaveTextContent(/50[\.\u00A0]000,00/);
    });
  });

  it("muestra un estado de carga inicial", () => {
    renderSidebar();

    expect(screen.getAllByText(/actualizando/i).length).toBeGreaterThan(0);
  });

  it("muestra error cuando la API de mercado falla", async () => {
    server.use(
      makeMarketErrorHandler("crypto"),
      makeMarketErrorHandler("stocks"),
      makeMarketErrorHandler("forex")
    );

    renderSidebar();

    const errors = await screen.findAllByText(/error/i);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("muestra error cuando no hay datos disponibles", async () => {
    server.use(
      makeMarketEmptyHandler("crypto"),
      makeMarketEmptyHandler("stocks"),
      makeMarketEmptyHandler("forex")
    );

    renderSidebar();

    const errors = await screen.findAllByText(/error/i);
    expect(errors.length).toBeGreaterThan(0);
  });

  it("actualiza precios tras revalidación manual", async () => {
    jest.useFakeTimers();
    try {
      renderSidebar();

      expect(await screen.findByText(/50\.000,00/)).toBeInTheDocument();

      server.use(
        makeMarketQuoteHandler("crypto", { price: 51_000, raw_change: 3.1 })
      );

      await act(async () => {
        jest.advanceTimersByTime(31_000);
      });

      await waitFor(() => {
        const updatedPrice = screen
          .getByText("BTCUSDT")
          .parentElement?.parentElement?.querySelector("div.text-right > p");
        expect(updatedPrice).toHaveTextContent(/51[\.\u00A0]000,00/);
      });
    } finally {
      jest.useRealTimers();
    }
  });
});
