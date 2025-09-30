"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { getAlertsWebSocketUrl } from "@/lib/api";

export type AlertWebSocketEvent = {
  type: string;
  [key: string]: unknown;
};

export type AlertWebSocketStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";

interface UseAlertsWebSocketOptions {
  token?: string | null;
  enabled?: boolean;
  onAlert?: (event: AlertWebSocketEvent) => void;
  onSystemMessage?: (event: AlertWebSocketEvent) => void;
}

interface UseAlertsWebSocketResult {
  status: AlertWebSocketStatus;
  lastMessage: AlertWebSocketEvent | null;
  error: string | null;
  reconnect: () => void;
  disconnect: () => void;
}

export function useAlertsWebSocket({
  token,
  enabled = true,
  onAlert,
  onSystemMessage,
}: UseAlertsWebSocketOptions = {}): UseAlertsWebSocketResult {
  const [status, setStatus] = useState<AlertWebSocketStatus>("idle");
  const [lastMessage, setLastMessage] =
    useState<AlertWebSocketEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttempts = useRef(0);
  const manualClose = useRef(false);

  const url = useMemo(() => {
    if (!enabled) {
      return null;
    }
    try {
      return getAlertsWebSocketUrl(token ?? undefined);
    } catch (err) {
      console.error("No se pudo construir la URL del WebSocket", err);
      return null;
    }
  }, [enabled, token]);

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      window.clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!url) {
      return;
    }
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    manualClose.current = false;
    setStatus("connecting");
    setError(null);

    const socket = new WebSocket(url);
    wsRef.current = socket;

    socket.onopen = () => {
      reconnectAttempts.current = 0;
      setStatus("open");
    };

    socket.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as AlertWebSocketEvent;
        setLastMessage(data);
        if (data.type === "alert" && onAlert) {
          onAlert(data);
        } else if (data.type === "system" && onSystemMessage) {
          onSystemMessage(data);
        }
      } catch (err) {
        console.error("Mensaje WS no parseable", err);
        setError("Mensaje de WebSocket no válido");
      }
    };

    socket.onerror = () => {
      setStatus("error");
      setError("Ocurrió un error con la conexión en vivo");
    };

    socket.onclose = () => {
      setStatus("closed");
      wsRef.current = null;
      if (!manualClose.current) {
        reconnectAttempts.current += 1;
        const delay = Math.min(
          1000 * 2 ** (reconnectAttempts.current - 1),
          15000
        );
        if (reconnectTimeoutRef.current) {
          window.clearTimeout(reconnectTimeoutRef.current);
        }
        reconnectTimeoutRef.current = window.setTimeout(() => {
          reconnectTimeoutRef.current = null;
          connect();
        }, delay);
      }
    };
  }, [enabled, onAlert, onSystemMessage, url]);

  const disconnect = useCallback(() => {
    manualClose.current = true;
    cleanup();
    const socket = wsRef.current;
    if (socket && socket.readyState !== WebSocket.CLOSED) {
      socket.close();
    }
    wsRef.current = null;
    setStatus("closed");
  }, [cleanup]);

  useEffect(() => {
    if (!enabled) {
      disconnect();
      return undefined;
    }

    connect();

    return () => {
      manualClose.current = true;
      cleanup();
      const socket = wsRef.current;
      if (socket && socket.readyState !== WebSocket.CLOSED) {
        socket.close();
      }
      wsRef.current = null;
    };
  }, [connect, cleanup, disconnect, enabled, url]);

  const reconnect = useCallback(() => {
    manualClose.current = false;
    cleanup();
    connect();
  }, [cleanup, connect]);

  return { status, lastMessage, error, reconnect, disconnect };
}

export type { UseAlertsWebSocketResult };
