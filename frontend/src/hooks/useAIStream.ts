"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface AIInsight {
  id: string;
  message: string;
  timestamp: string;
  source: "stream" | "realtime" | "manual";
  raw?: unknown;
}

interface UseAIStreamOptions {
  enabled?: boolean;
  token?: string;
  realtimePayload?: unknown;
  onInsight?: (insight: AIInsight) => void;
}

// ✅ Codex fix: hook para gestionar el stream SSE y los insights provenientes del WebSocket
export function useAIStream({
  enabled = true,
  token,
  realtimePayload,
  onInsight,
}: UseAIStreamOptions = {}) {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  const pushInsight = useCallback(
    (payload: { message: string; source: AIInsight["source"]; raw?: unknown; timestamp?: string }) => {
      if (!payload.message) {
        return;
      }

      const insight: AIInsight = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        message: payload.message,
        timestamp: payload.timestamp ?? new Date().toISOString(),
        source: payload.source,
        raw: payload.raw,
      };

      setInsights((previous) => [...previous, insight]);
      onInsight?.(insight);
    },
    [onInsight]
  );

  useEffect(() => {
    if (!enabled) {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setConnected(false);
      return;
    }

    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      return;
    }

    const baseUrl = new URL("/api/ai/stream", window.location.origin);
    if (token) {
      baseUrl.searchParams.set("token", token);
    }

    const eventSource = new EventSource(baseUrl.toString());
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setConnected(true);
      setError(null);
    };

    eventSource.onmessage = (event) => {
      const rawData = event.data;
      if (!rawData) {
        return;
      }

      let message: string | null = null;
      let raw: unknown = rawData;

      try {
        const parsed = JSON.parse(rawData);
        raw = parsed;
        if (parsed && typeof parsed === "object") {
          const candidate =
            typeof (parsed as Record<string, unknown>).message === "string"
              ? (parsed as Record<string, unknown>).message
              : typeof (parsed as Record<string, unknown>).content === "string"
              ? (parsed as Record<string, unknown>).content
              : null;
          if (candidate) {
            message = candidate;
          }
        } else if (typeof parsed === "string") {
          message = parsed;
        }
      } catch (error) {
        message = rawData;
      }

      if (message) {
        pushInsight({ message, source: "stream", raw });
      }
    };

    eventSource.onerror = () => {
      setConnected(false);
      setError("stream_error");
      eventSource.close();
      eventSourceRef.current = null;
    };

    return () => {
      setConnected(false);
      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [enabled, pushInsight, token]);

  useEffect(() => {
    if (!realtimePayload || typeof realtimePayload !== "object") {
      return;
    }

    const payload = realtimePayload as Record<string, unknown>;
    if (payload.type !== "insight") {
      return;
    }

    const message =
      typeof payload.content === "string"
        ? payload.content
        : typeof payload.message === "string"
        ? payload.message
        : null;

    if (!message) {
      return;
    }

    pushInsight({
      message,
      source: "realtime",
      raw: realtimePayload,
      timestamp: typeof payload.timestamp === "string" ? payload.timestamp : undefined,
    });

    if (typeof process !== "undefined" && process.env.NODE_ENV !== "production") {
      console.log("AI Insight recibido:", message);
    }
  }, [pushInsight, realtimePayload]);

  const addInsight = useCallback(
    (message: string, options?: { timestamp?: string }) => {
      pushInsight({
        message,
        source: "manual",
        raw: { message },
        timestamp: options?.timestamp,
      });
    },
    [pushInsight]
  );

  return {
    connected,
    error,
    insights,
    addInsight,
  } as const;
}
