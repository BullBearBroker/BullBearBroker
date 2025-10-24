// 🧩 Bloque 8B
"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "@/lib/motion";
import { BellRing, Beaker, History, Inbox, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import NotificationsDebugPanel from "@/components/debug/NotificationsDebugPanel";
import { PERMISSION_DENIED_MESSAGE, usePushNotifications } from "@/hooks/usePushNotifications";
// 🧩 Bloque 9B
import { useLiveNotifications } from "@/hooks/useLiveNotifications";
// 🧩 Bloque 9B
import { useAuth } from "@/components/providers/auth-provider";
import { useOptionalUIState } from "@/hooks/useUIState";

export interface NotificationLog {
  id: string;
  title: string;
  body: string;
  timestamp: number;
}

const STORAGE_KEY = "notificationHistory";

export default function NotificationCenterCard() {
  // 🧩 Bloque 9B
  const { token } = useAuth();
  const push = usePushNotifications(token ?? undefined);
  const {
    error,
    permission,
    requestPermission,
    sendTestNotification,
    notificationHistory,
    clearLogs,
  } = push;
  // 🧩 Bloque 9B
  const { events, status } = useLiveNotifications(token ?? undefined);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
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

  useEffect(() => {
    if (permission === "denied") {
      setToastMessage(PERMISSION_DENIED_MESSAGE);
    }
  }, [permission]);

  useEffect(() => {
    if (!error) {
      return;
    }
    setToastMessage(error);
  }, [error]);

  useEffect(() => {
    if (!toastMessage) {
      return;
    }
    const timeout = window.setTimeout(() => setToastMessage(null), 5000);
    return () => window.clearTimeout(timeout);
  }, [toastMessage]);

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
        const numericTimestamp =
          typeof rawTimestamp === "number"
            ? rawTimestamp
            : Number.isFinite(Date.parse(rawTimestamp))
              ? Date.parse(rawTimestamp)
              : Date.now();

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

  const isRealtime = status === "connected";
  const uiState = useOptionalUIState();
  const setToastVisible = uiState?.setToastVisible;
  const debugFlag = process.env.NEXT_PUBLIC_FEATURE_NOTIFICATIONS_DEBUG;
  const showDebugPanel =
    process.env.NODE_ENV !== "production" && (debugFlag === undefined || debugFlag !== "false");

  useEffect(() => {
    if (!setToastVisible) {
      return;
    }

    setToastVisible(Boolean(toastMessage));
    return () => {
      if (toastMessage) {
        setToastVisible(false);
      }
    };
  }, [setToastVisible, toastMessage]);

  return (
    <Card className="surface-card">
      <AnimatePresence>
        {toastMessage ? (
          <motion.div
            key="notification-toast"
            role="alert"
            initial={{ opacity: 0, scale: 0.9, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 12 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="fixed bottom-6 right-6 z-50 max-w-sm rounded-xl border border-border/60 bg-background/90 px-4 py-3 text-sm text-foreground shadow-lg backdrop-blur"
          >
            {toastMessage}
          </motion.div>
        ) : null}
      </AnimatePresence>
      <CardHeader className="space-y-3 pb-4">
        <div className="flex flex-col gap-2">
          <CardTitle className="flex items-center gap-2 text-lg font-sans font-medium tracking-tight">
            <BellRing className="h-5 w-5 text-primary" aria-hidden="true" />
            Notificaciones en vivo
          </CardTitle>
          <CardDescription className="text-sm text-muted-foreground">
            Gestiona la suscripción push y consulta el historial consolidado de eventos.
          </CardDescription>
        </div>
        <Badge
          variant={isRealtime ? "outline" : "secondary"}
          className="w-fit rounded-full px-3 py-1 text-xs font-medium"
        >
          {isRealtime ? "Canal en tiempo real" : "Canal en modo seguro"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2 md:grid-cols-3">
          <Button
            type="button"
            variant="secondary"
            className="flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={() => void requestPermission()}
          >
            <BellRing className="h-4 w-4" aria-hidden="true" />
            Activar push
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={() => void sendTestNotification()}
          >
            <Beaker className="h-4 w-4" aria-hidden="true" />
            Enviar prueba
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            onClick={() => {
              clearLogs();
              setHistory([]);
            }}
          >
            <Trash2 className="h-4 w-4" aria-hidden="true" />
            Limpiar
          </Button>
        </div>

        <div className="space-y-2 rounded-xl border border-border/50 bg-[hsl(var(--surface))] p-3">
          <div className="flex items-center justify-between">
            <p className="flex items-center gap-2 text-sm font-medium text-card-foreground">
              <History className="h-4 w-4 text-primary" aria-hidden="true" /> Historial reciente
            </p>
            <span className="text-xs text-muted-foreground">{history.length} eventos</span>
          </div>
          <ScrollArea className="max-h-56">
            <div className="space-y-2 pr-2">
              {history.length === 0 ? (
                <p className="text-sm text-muted-foreground">Sin notificaciones aún.</p>
              ) : (
                history
                  .slice()
                  .reverse()
                  .map((n) => (
                    <div
                      key={n.id}
                      className="rounded-lg border border-border/40 bg-[hsl(var(--surface-muted))] p-3 text-sm text-card-foreground"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium">{n.title}</p>
                        <span className="text-xs text-muted-foreground">
                          {new Date(n.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      {n.body && (
                        <p className="mt-1 text-xs text-muted-foreground leading-relaxed">
                          {n.body}
                        </p>
                      )}
                    </div>
                  ))
              )}
            </div>
          </ScrollArea>
        </div>

        <div className="grid gap-2 rounded-xl border border-border/40 bg-[hsl(var(--surface))] p-3 text-xs text-muted-foreground">
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-2 font-medium text-card-foreground">
              <Inbox className="h-4 w-4 text-primary" aria-hidden="true" /> Estado de permisos
            </span>
            <Badge variant="outline" className="rounded-full px-2 py-0.5 text-[10px] uppercase">
              {permission}
            </Badge>
          </div>
          <p>
            Canal actual:{" "}
            <span className="font-medium text-card-foreground">
              {isRealtime ? "Tiempo real" : "Fallback"}
            </span>
          </p>
        </div>
      </CardContent>
      {showDebugPanel ? (
        <div className="border-t border-border/40 p-4">
          <NotificationsDebugPanel pushState={push} token={token ?? undefined} />
        </div>
      ) : null}
    </Card>
  );
}
