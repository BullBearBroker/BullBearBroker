// 🧩 Bloque 8B
"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePushNotifications } from "@/hooks/usePushNotifications";
// 🧩 Bloque 9B
import { useLiveNotifications } from "@/hooks/useLiveNotifications";
// 🧩 Bloque 9B
import { useAuth } from "@/components/providers/auth-provider";

export interface NotificationLog {
  id: string;
  title: string;
  body: string;
  timestamp: number;
}

const STORAGE_KEY = "notificationHistory";

export default function NotificationCenterCard() {
  const {
    permission,
    requestPermission,
    sendTestNotification,
    notificationHistory,
    clearLogs,
  } = usePushNotifications();
  // 🧩 Bloque 9B
  const { token } = useAuth();
  // 🧩 Bloque 9B
  const { events, status } = useLiveNotifications(token ?? undefined);
  const [history, setHistory] = useState<NotificationLog[]>(() => {
    if (typeof window === "undefined") {
      return notificationHistory;
    }
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (!stored) {
        return notificationHistory;
      }
      const parsed = JSON.parse(stored) as NotificationLog[];
      if (!Array.isArray(parsed)) {
        return notificationHistory;
      }
      return parsed;
    } catch (err) {
      console.error("No se pudo cargar el historial de notificaciones", err);
      return notificationHistory;
    }
  });

  // 🧩 Bloque 8B
  useEffect(() => {
    if (!notificationHistory.length) {
      setHistory([]);
      return;
    }
    setHistory((prev) => {
      const map = new Map<string, NotificationLog>();
      for (const entry of prev) {
        map.set(entry.id, entry);
      }
      let changed = false;
      for (const entry of notificationHistory) {
        const existing = map.get(entry.id);
        if (
          !existing ||
          existing.timestamp !== entry.timestamp ||
          existing.body !== entry.body ||
          existing.title !== entry.title
        ) {
          map.set(entry.id, entry);
          changed = true;
        }
      }
      if (!changed && map.size === prev.length) {
        return prev;
      }
      const ordered = Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);
      return ordered;
    });
  }, [notificationHistory]);

  // 🧩 Bloque 8B
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (history.length === 0) {
      window.localStorage.removeItem(STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  // 🧩 Bloque 9B
  useEffect(() => {
    if (!events.length) {
      return;
    }
    setHistory((prev) => {
      const map = new Map(prev.map((item) => [item.id, item]));
      let changed = false;

      for (const event of events) {
        const rawTimestamp = event.timestamp;
        const numericTimestamp = (
          typeof rawTimestamp === "number"
            ? rawTimestamp
            : Number.isFinite(Date.parse(rawTimestamp))
            ? Date.parse(rawTimestamp)
            : Date.now()
        );

        const entry: NotificationLog = {
          id: event.id,
          title: event.title,
          body: event.body,
          timestamp: numericTimestamp,
        };

        const existing = map.get(entry.id);
        if (
          !existing ||
          existing.timestamp !== entry.timestamp ||
          existing.body !== entry.body ||
          existing.title !== entry.title
        ) {
          map.set(entry.id, entry);
          changed = true;
        }
      }

      if (!changed && map.size === prev.length) {
        return prev;
      }

      return Array.from(map.values()).sort((a, b) => a.timestamp - b.timestamp);
    });
  }, [events]);

  return (
    <Card className="p-4 shadow-md rounded-2xl">
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Centro de Notificaciones</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <Button onClick={() => void requestPermission()}>🔔 Activar Push</Button>
          <Button onClick={() => void sendTestNotification()} variant="secondary">
            🧪 Enviar Test
          </Button>
          <Button
            onClick={() => {
              clearLogs();
              setHistory([]);
            }}
            variant="destructive"
          >
            🧹 Limpiar
          </Button>
        </div>

        <div className="max-h-64 overflow-y-auto border rounded-lg p-2 bg-muted/40">
          {history.length === 0 ? (
            <p className="text-sm text-muted-foreground">Sin notificaciones aún.</p>
          ) : (
            history
              .slice()
              .reverse()
              .map((n) => (
                <div key={n.id} className="border-b last:border-0 py-1 text-sm leading-tight">
                  <span className="font-semibold">{n.title}</span> — {n.body}{" "}
                  <span className="text-xs text-muted-foreground">
                    ({new Date(n.timestamp).toLocaleTimeString()})
                  </span>
                </div>
              ))
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Estado: <strong>{permission}</strong>
        </p>
        <p className="text-xs text-muted-foreground">
          Estado:{" "}
          <strong>
            {status === "connected"
              ? "🟢 Conectado (Tiempo real)"
              : "🟡 Fallback (Polling)"}
          </strong>
        </p>
      </CardContent>
    </Card>
  );
}
