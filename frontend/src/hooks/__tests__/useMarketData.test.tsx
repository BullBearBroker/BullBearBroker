import { act, renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";
import { http, HttpResponse } from "msw";

import { useMarketData } from "../useMarketData";
import { server } from "@/tests/msw/server";
import {
  makeMarketEmptyHandler,
  makeMarketErrorHandler,
  makeMarketQuoteHandler,
} from "@/tests/msw/handlers";

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
    {children}
  </SWRConfig>
);

describe("useMarketData", () => {
  afterEach(() => {
    server.resetHandlers();
  });

  it("retorna datos cuando la API responde", async () => {
    const { result } = renderHook(
      () => useMarketData({ type: "crypto", symbol: "BTC", token: "token" }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.symbol).toBe("BTCUSDT");
    expect(result.current.error).toBeUndefined();
  });

  it("retorna error cuando la API queda vacía", async () => {
    server.use(makeMarketEmptyHandler("crypto"));

    const { result } = renderHook(
      () => useMarketData({ type: "crypto", symbol: "BTC", token: "token" }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("maneja respuestas 500", async () => {
    server.use(makeMarketErrorHandler("crypto"));

    const { result } = renderHook(
      () => useMarketData({ type: "crypto", symbol: "BTC", token: "token" }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("permite refrescar manualmente los datos", async () => {
    server.use(makeMarketQuoteHandler("crypto", { price: 50_000 }));

    const { result } = renderHook(
      () => useMarketData({ type: "crypto", symbol: "BTC", token: "token" }),
      { wrapper }
    );

    await waitFor(() => expect(result.current.data?.price).toBe(50_000));

    server.use(makeMarketQuoteHandler("crypto", { price: 51_000 }));
    await act(async () => {
      await result.current.refresh();
    });

    await waitFor(() => expect(result.current.data?.price).toBe(51_000));
  });

  it("no realiza consultas cuando está deshabilitado", async () => {
    const abortHandler = jest.fn();
    server.use(
      http.get(
        "*/api/markets/crypto/prices",
        ({ request }) => {
          abortHandler(request.url);
          return HttpResponse.json({ quotes: [] });
        }
      )
    );

    const { result } = renderHook(
      () => useMarketData({ type: "crypto", symbol: "BTC", enabled: false }),
      { wrapper }
    );

    expect(result.current.isLoading).toBe(false);
    expect(result.current.data).toBeUndefined();
    expect(abortHandler).not.toHaveBeenCalled();
  });
});
