// 🧩 Bloque 9B
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function useLiveNotifications(token?: string | null) {
  const [events, setEvents] = useState<NotificationEvent[]>([]);
  const [status, setStatus] = useState<"connected" | "fallback">("fallback");
  const socketRef = useRef<WebSocket | null>(null);

  const wsUrl = useMemo(() => {
    if (!token || typeof window === "undefined") {
      return null;
    }
    const origin = window.location.origin.replace("http", "ws");
    const encodedToken = encodeURIComponent(token);
    return `${origin}/ws/notifications?token=${encodedToken}`;
  }, [token]);

  const { data: fallbackData } = useSWR<NotificationEvent[]>(
    status === "fallback" ? "/api/notifications/logs" : null,
    fetcher,
    { refreshInterval: 5000 }
  );

  useEffect(() => {
    if (status !== "fallback") {
      return;
    }
    if (!fallbackData) {
      return;
    }
    if (!Array.isArray(fallbackData)) {
      console.warn("Invalid fallback payload for notifications");
      return;
    }
    setEvents(fallbackData);
  }, [fallbackData, status]);

  useEffect(() => {
    if (!wsUrl) {
      setStatus("fallback");
      return;
    }

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;
    let active = true;

    ws.onopen = () => {
      if (!active) return;
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      if (!active) {
        return;
      }
      try {
        const data = JSON.parse(event.data) as NotificationEvent;
        setEvents((prev) => [...prev, data]);
      } catch (error) {
        console.warn("Invalid WS message:", error);
      }
    };

    const handleFallback = () => {
      if (!active) return;
      setStatus("fallback");
    };

    ws.onerror = handleFallback;
    ws.onclose = handleFallback;

    return () => {
      active = false;
      ws.close();
      if (socketRef.current === ws) {
        socketRef.current = null;
      }
    };
  }, [wsUrl]);

  return { events, status };
}

export interface NotificationEvent {
  id: string;
  title: string;
  body: string;
  timestamp: string | number;
  meta?: Record<string, unknown>;
}
