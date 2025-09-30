"use client";

import useSWR, { type SWRResponse } from "swr";

import type { HistoricalDataResponse } from "@/lib/api";
import { getHistoricalData } from "@/lib/api";

export interface UseHistoricalDataOptions {
  interval?: string;
  limit?: number;
  market?: "auto" | "crypto" | "stock" | "equity" | "forex";
  refreshInterval?: number;
}

type HistoricalSWR = SWRResponse<HistoricalDataResponse, Error>;

export interface UseHistoricalDataResult {
  data?: HistoricalDataResponse;
  error?: Error;
  isLoading: boolean;
  isValidating: boolean;
  refresh: HistoricalSWR["mutate"];
  mutate: HistoricalSWR["mutate"];
  isEmpty: boolean;
}

export function useHistoricalData(
  symbol?: string | null,
  options: UseHistoricalDataOptions = {}
): UseHistoricalDataResult {
  const interval = options.interval ?? "1h";
  const limit = options.limit ?? 240;
  const market = options.market ?? "auto";

  const swr = useSWR<HistoricalDataResponse, Error>(
    symbol ? ["history", symbol, interval, limit, market] : null,
    ([, sym, int, lim, mkt]) =>
      getHistoricalData(sym as string, {
        interval: int as string,
        limit: Number(lim),
        market: mkt as UseHistoricalDataOptions["market"],
      }),
    {
      revalidateOnFocus: false,
      refreshInterval: options.refreshInterval,
    }
  );

  return {
    data: swr.data,
    error: swr.error,
    isLoading: swr.isLoading,
    isValidating: swr.isValidating,
    refresh: swr.mutate,
    mutate: swr.mutate,
    isEmpty: !swr.data || swr.data.values.length === 0,
  };
}
