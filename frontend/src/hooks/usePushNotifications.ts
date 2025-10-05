"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { subscribePush, testNotificationDispatcher } from "@/lib/api";

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");

  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export interface NotificationEnvelope {
  id: string;
  title: string;
  body: string;
  payload?: Record<string, unknown>;
  receivedAt: string;
}

interface PushNotificationsState {
  enabled: boolean;
  error: string | null;
  permission: NotificationPermission | "unsupported";
  loading: boolean;
  testing: boolean;
  events: NotificationEnvelope[];
  logs: string[];
  lastEvent: NotificationEnvelope | null;
  sendTestNotification: () => Promise<void>;
  requestPermission: () => Promise<NotificationPermission | "unsupported">;
  dismissEvent: (id: string) => void;
}

function makeId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function nowLabel() {
  return new Date().toLocaleTimeString();
}

export function usePushNotifications(token?: string | null): PushNotificationsState {
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [events, setEvents] = useState<NotificationEnvelope[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [permission, setPermission] = useState<
    NotificationPermission | "unsupported"
  >(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return "unsupported";
    }
    return Notification.permission;
  });

  const appendLog = useCallback((message: string) => {
    setLogs((prev) => {
      const next = [...prev, `[${nowLabel()}] ${message}`];
      return next.slice(-25);
    });
  }, []);

  const dismissEvent = useCallback((id: string) => {
    setEvents((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const requestPermission = useCallback(async () => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setPermission("unsupported");
      return "unsupported";
    }

    const result = await Notification.requestPermission();
    setPermission(result);
    appendLog(
      result === "granted"
        ? "Permiso de notificaciones concedido"
        : result === "denied"
        ? "Permiso de notificaciones denegado"
        : "Permiso de notificaciones pendiente"
    );
    return result;
  }, [appendLog]);

  useEffect(() => {
    if (!token) return;
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      setError("Las notificaciones push no están soportadas en este navegador.");
      return;
    }

    let active = true;
    const vapidKey = process.env.NEXT_PUBLIC_VAPID_KEY;
    if (!vapidKey) {
      setError("Falta configurar la clave pública VAPID.");
      return;
    }

    const register = async () => {
      setLoading(true);
      try {
        const registration = await navigator.serviceWorker.register("/sw.js");
        let permissionState = Notification.permission;
        setPermission(permissionState);
        if (permissionState === "denied") {
          appendLog("Permiso de notificaciones denegado");
        }
        if (permissionState !== "granted") {
          permissionState = await Notification.requestPermission();
          setPermission(permissionState);
        }
        if (permissionState !== "granted") {
          if (active) {
            setError("Debes habilitar las notificaciones para recibir alertas.");
            setEnabled(false);
          }
          return;
        }

        let subscription = await registration.pushManager.getSubscription();
        if (!subscription) {
          subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey),
          });
        }

        const json = subscription.toJSON();
        const auth = json.keys?.auth ?? "";
        const p256dh = json.keys?.p256dh ?? "";

        const expirationTime =
          typeof subscription.expirationTime === "number"
            ? new Date(subscription.expirationTime).toISOString()
            : null; // ✅ Codex fix: normalizamos el timestamp a ISO8601 antes de enviarlo.

        await subscribePush(
          {
            endpoint: subscription.endpoint,
            expirationTime,
            keys: { auth, p256dh },
          },
          token
        );

        if (active) {
          setEnabled(true);
          setError(null);
          appendLog("Suscripción push activa");
        }
      } catch (err) {
        if (!active) return;
        console.error("No se pudo registrar la suscripción push", err);
        const message =
          err instanceof Error ? err.message : "No se pudo registrar la suscripción push.";
        setError(message);
        setEnabled(false);
        appendLog(`Error al registrar push: ${message}`);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    register();

    return () => {
      active = false;
    };
  }, [appendLog, token]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const container = navigator.serviceWorker as unknown as
      | (ServiceWorkerContainer & EventTarget)
      | undefined;
    if (!container || typeof container.addEventListener !== "function") {
      return;
    }

    const handleMessage = (event: MessageEvent) => {
      const data = event.data;
      if (!data || typeof data !== "object") return;
      const type = (data as { type?: string }).type;
      if (type !== "notification:dispatcher" && type !== "push-notification") {
        return;
      }

      const title =
        typeof (data as Record<string, unknown>).title === "string"
          ? ((data as Record<string, unknown>).title as string)
          : "Notificación";
      const body =
        typeof (data as Record<string, unknown>).body === "string"
          ? ((data as Record<string, unknown>).body as string)
          : "";
      const payload =
        typeof (data as Record<string, unknown>).payload === "object"
          ? ((data as Record<string, unknown>).payload as Record<string, unknown>)
          : undefined;
      const receivedAt =
        typeof (data as Record<string, unknown>).receivedAt === "string"
          ? ((data as Record<string, unknown>).receivedAt as string)
          : new Date().toISOString();

      const envelope: NotificationEnvelope = {
        id: makeId(),
        title,
        body,
        payload,
        receivedAt,
      };

      setEvents((prev) => [...prev, envelope]);
      appendLog(`Evento recibido: ${title}`);
      console.log("Push recibido correctamente", envelope);
    };

    container.addEventListener("message", handleMessage as EventListener);

    return () => {
      container.removeEventListener("message", handleMessage as EventListener);
    };
  }, [appendLog]);

  const sendTestNotification = useCallback(async () => {
    if (!token) {
      appendLog("No se puede enviar prueba sin token de autenticación");
      return;
    }

    try {
      setTesting(true);
      await testNotificationDispatcher(token);
      appendLog("Solicitud de notificación de prueba enviada");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo enviar la notificación de prueba";
      setError(message);
      appendLog(`Error al enviar prueba: ${message}`);
    } finally {
      setTesting(false);
    }
  }, [appendLog, token]);

  const lastEvent = useMemo(() => {
    return events.length > 0 ? events[events.length - 1] : null;
  }, [events]);

  return {
    enabled,
    error,
    permission,
    loading,
    testing,
    events,
    logs,
    lastEvent,
    sendTestNotification,
    requestPermission,
    dismissEvent,
  };
}
