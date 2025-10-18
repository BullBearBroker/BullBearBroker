"use client";

import { useEffect, useRef, useState } from "react";

// ✅ Codex fix: hook para gestionar conexión WebSocket en tiempo real
export function useRealtime() {
  const socketRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [data, setData] = useState<any>(null); // ✅ Codex fix: estado flexible para payloads dinámicos

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
    const wsBase = apiBase.replace(/^http/i, "ws");
    const wsUrl = `${wsBase.replace(/\/$/, "")}/api/realtime/ws`;

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data as string);
        setData(msg);
      } catch (error) {
        console.error("Invalid WS message", error);
      }
    };

    ws.onerror = () => {
      setConnected(false);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      socketRef.current = null; // ✅ Codex fix: limpiar referencia cuando se desmonta el hook
      ws.close();
    };
  }, []);

  return { connected, data } as const;
}
