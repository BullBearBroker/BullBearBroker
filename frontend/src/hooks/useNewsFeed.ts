"use client";

import useSWR from "swr";

import { listNews, NewsItem } from "@/lib/api";

interface UseNewsFeedOptions {
  token?: string | null;
  enabled?: boolean;
}

interface UseNewsFeedResult {
  data: NewsItem[] | undefined;
  error: Error | undefined;
  isLoading: boolean;
  refresh: () => Promise<NewsItem[] | undefined>;
}

export function useNewsFeed({ token, enabled = true }: UseNewsFeedOptions = {}): UseNewsFeedResult {
  const swrKey = enabled ? ["news-feed", token ?? null] : null;

  const { data, error, isLoading, mutate } = useSWR<NewsItem[]>(
    swrKey,
    () => listNews(token ?? undefined),
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

export type { UseNewsFeedResult };
