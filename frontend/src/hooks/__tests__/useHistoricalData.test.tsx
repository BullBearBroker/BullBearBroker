import React from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { SWRConfig } from "swr";

import { useHistoricalData } from "../useHistoricalData";
import { getHistoricalData } from "@/lib/api";

jest.mock("@/lib/api", () => ({
  getHistoricalData: jest.fn(),
}));

const mockGetHistoricalData = getHistoricalData as jest.Mock;

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <SWRConfig value={{ provider: () => new Map() }}>{children}</SWRConfig>
);

describe("useHistoricalData", () => {
  beforeEach(() => {
    mockGetHistoricalData.mockReset();
  });

  it("obtiene datos históricos y los expone en el hook", async () => {
    const sample = {
      symbol: "BTCUSDT",
      interval: "1h",
      source: "Binance",
      values: [
        { timestamp: "2024-01-01T00:00:00Z", open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
      ],
    };
    mockGetHistoricalData.mockResolvedValue(sample);

    const { result } = renderHook(() => useHistoricalData("BTCUSDT"), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(sample);
    });
    expect(result.current.isEmpty).toBe(false);
    expect(mockGetHistoricalData).toHaveBeenCalledWith("BTCUSDT", {
      interval: "1h",
      limit: 240,
      market: "auto",
    });
  });

  it("propaga errores provenientes del API", async () => {
    mockGetHistoricalData.mockRejectedValue(new Error("fallo"));

    const { result } = renderHook(() => useHistoricalData("ETHUSDT"), { wrapper });

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
    });
    expect(result.current.data).toBeUndefined();
  });

  it("permite refrescar manualmente los datos", async () => {
    const sample = {
      symbol: "BTCUSDT",
      interval: "1h",
      source: "Binance",
      values: [],
    };
    mockGetHistoricalData.mockResolvedValue(sample);

    const { result } = renderHook(() => useHistoricalData("BTCUSDT"), { wrapper });

    await waitFor(() => {
      expect(result.current.data).toEqual(sample);
    });

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockGetHistoricalData).toHaveBeenCalledTimes(2);
  });
});
