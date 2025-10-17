"use client";

import useSWR from "swr";

import { getMarketQuote, MarketQuote } from "@/lib/api";

type MarketType = "crypto" | "stock" | "forex";

interface UseMarketDataOptions {
  type: MarketType;
  symbol: string;
  token?: string | null;
  enabled?: boolean;
}

interface UseMarketDataResult {
  data: MarketQuote | undefined;
  error: Error | undefined;
  isLoading: boolean;
  refresh: () => Promise<MarketQuote | undefined>;
}

export function useMarketData({
  type,
  symbol,
  token,
  enabled = true,
}: UseMarketDataOptions): UseMarketDataResult {
  const swrKey = enabled ? ["market-data", type, symbol, token ?? null] : null;

  const { data, error, isLoading, mutate } = useSWR<MarketQuote>(
    swrKey,
    () => getMarketQuote(type, symbol, token ?? undefined),
    {
      revalidateOnFocus: false,
    },
  );

  return {
    data,
    error,
    isLoading,
    refresh: () => mutate(),
  };
}

export type { UseMarketDataResult };
