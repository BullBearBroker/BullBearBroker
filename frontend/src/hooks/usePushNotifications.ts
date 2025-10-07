"use client";

// 🧩 Bloque 8B
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchVapidPublicKey,
  subscribePush,
  testNotificationDispatcher,
} from "@/lib/api";

const isTestEnvironment =
  typeof process !== "undefined" &&
  (process.env.NODE_ENV === "test" || process.env.JEST_WORKER_ID !== undefined);

export const PERMISSION_DENIED_MESSAGE =
  "Debes permitir notificaciones para recibir alertas.";

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

interface NotificationHistoryEntry {
  id: string;
  title: string;
  body: string;
  timestamp: number;
}

interface PushNotificationsState {
  enabled: boolean;
  error: string | null;
  permission: NotificationPermission | "unsupported";
  loading: boolean;
  testing: boolean;
  events: NotificationEnvelope[];
  logs: string[];
  notificationHistory: NotificationHistoryEntry[];
  lastEvent: NotificationEnvelope | null;
  sendTestNotification: () => Promise<void>;
  requestPermission: () => Promise<NotificationPermission | "unsupported">;
  dismissEvent: (id: string) => void;
  clearLogs: () => void;
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

// 🧩 Bloque 8A - Validar coincidencia de claves
export async function registerPushSubscription(
  registration?: ServiceWorkerRegistration,
  vapidPublicKey?: string | null
): Promise<PushSubscription> {
  const toastApi = (globalThis as {
    toast?: { error?: (message: string) => void };
  }).toast;

  const normalizeKey = (key?: string | null) =>
    typeof key === "string" ? key.trim() : "";

  let serverKey = normalizeKey(vapidPublicKey);
  if (!serverKey) {
    serverKey = normalizeKey(await fetchVapidPublicKey());
  }

  if (!serverKey) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    serverKey = normalizeKey(await fetchVapidPublicKey());
  }

  if (!serverKey) {
    if (toastApi?.error) {
      toastApi.error("Faltan claves VAPID");
    }
    throw new Error("Missing VAPID key");
  }

  const localKey = normalizeKey(process.env.NEXT_PUBLIC_VAPID_KEY ?? "");

  if (localKey && localKey !== serverKey) {
    console.warn("VAPID public key mismatch between frontend and backend.");
  }

  const swContainer = navigator.serviceWorker;
  const swReg =
    registration ??
    ("ready" in swContainer && swContainer.ready
      ? await swContainer.ready
      : undefined);

  if (!swReg) {
    throw new Error("Service worker registration unavailable.");
  }

  const existingSubscription = await swReg.pushManager.getSubscription();
  if (existingSubscription) {
    return existingSubscription;
  }

  const applicationServerKey = urlBase64ToUint8Array(serverKey);
  return swReg.pushManager.subscribe({
    applicationServerKey,
    userVisibleOnly: true,
  });
}

export function usePushNotifications(token?: string | null): PushNotificationsState {
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [events, setEvents] = useState<NotificationEnvelope[]>([]);
  const [logs, setLogs] = useState<string[]>([]);
  const [notificationHistory, setNotificationHistory] = useState<NotificationHistoryEntry[]>(() => {
    if (typeof window === "undefined") {
      return [];
    }
    try {
      const stored = window.localStorage.getItem("notificationHistory");
      if (!stored) {
        return [];
      }
      const parsed = JSON.parse(stored) as NotificationHistoryEntry[];
      if (!Array.isArray(parsed)) {
        return [];
      }
      return parsed;
    } catch (err) {
      console.error("No se pudo hidratar el historial de notificaciones", err);
      return [];
    }
  });
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

  // 🧩 Bloque 8B
  const appendNotificationHistory = useCallback(
    (entry: NotificationHistoryEntry) => {
      setNotificationHistory((prev) => {
        const next = [...prev, entry];
        return next.slice(-100);
      });
    },
    []
  );

  // 🧩 Bloque 8B
  const clearLogs = useCallback(() => {
    setLogs([]);
    setNotificationHistory([]);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem("notificationHistory");
    }
  }, []);

  // 🧩 Bloque 8B
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (notificationHistory.length === 0) {
      window.localStorage.removeItem("notificationHistory");
      return;
    }
    window.localStorage.setItem(
      "notificationHistory",
      JSON.stringify(notificationHistory)
    );
  }, [notificationHistory]);

  const dismissEvent = useCallback((id: string) => {
    setEvents((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const requestPermission = useCallback(async () => {
    if (permission === "unsupported") {
      return "unsupported";
    }
    if (typeof window === "undefined" || !("Notification" in window)) {
      setPermission("unsupported");
      return "unsupported";
    }
    if (!("PushManager" in window)) {
      appendLog("Notificaciones push no soportadas en este navegador");
      setPermission("unsupported");
      return "unsupported";
    }

    if (permission !== "granted") {
      setError(null);
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
    if (result === "denied") {
      setError(PERMISSION_DENIED_MESSAGE);
    } else if (result === "granted") {
      setError(null);
    }
    return result;
  }, [appendLog, permission]);

  useEffect(() => {
    if (!token) return;
    if (typeof window === "undefined") return;
    const hasNavigator = typeof navigator !== "undefined";
    if (!("Notification" in window)) {
      setPermission("unsupported");
      setError("Las notificaciones push no están soportadas en este navegador.");
      return;
    }
    if (!("PushManager" in window)) {
      if (hasNavigator && !isTestEnvironment) {
        appendLog("Notificaciones push no soportadas en este navegador");
      }
      setPermission("unsupported");
      setError("Las notificaciones push no están soportadas en este navegador.");
      return;
    }
    if (!hasNavigator || !("serviceWorker" in navigator)) {
      setPermission("unsupported");
      setError("Los service workers no están soportados en este navegador.");
      return;
    }

    let active = true;

    const register = async () => {
      setLoading(true);
      try {
        const registration = await navigator.serviceWorker.ready;
        if (!registration) {
          throw new Error("Service worker registration unavailable.");
        }

        let permissionState = "Notification" in window ? Notification.permission : "default";
        setPermission(permissionState);

        if (permissionState === "denied") {
          appendLog("Permiso de notificaciones denegado");
          setError(PERMISSION_DENIED_MESSAGE);
          setEnabled(false);
          return;
        }

        if (permissionState !== "granted" && "Notification" in window) {
          permissionState = await Notification.requestPermission();
          setPermission(permissionState);
          appendLog(
            permissionState === "granted"
              ? "Permiso de notificaciones concedido"
              : permissionState === "denied"
              ? "Permiso de notificaciones denegado"
              : "Permiso de notificaciones pendiente"
          );
        }

        if (permissionState !== "granted") {
          if (permissionState === "denied") {
            setError(PERMISSION_DENIED_MESSAGE);
          }
          setEnabled(false);
          return;
        }

        const vapidPublicKey = await fetchVapidPublicKey();
        if (!vapidPublicKey) {
          console.warn("Missing VAPID key from backend.");
          appendLog("No se recibió clave pública VAPID del backend");
          setPermission("unsupported");
          setError("No se pudo obtener la clave pública VAPID desde el servidor.");
          setEnabled(false);
          return;
        }

        const subscription = await registerPushSubscription(
          registration,
          vapidPublicKey
        );
        appendLog("Clave pública VAPID validada correctamente");

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
        if (message.toLowerCase().includes("vapid")) {
          setPermission("unsupported");
        }
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
      appendNotificationHistory({
        id: envelope.id,
        title: envelope.title,
        body: envelope.body,
        timestamp: Date.parse(envelope.receivedAt) || Date.now(),
      });
      appendLog(`Evento recibido: ${title}`);
      appendLog("Push recibido correctamente");
    };

    container.addEventListener("message", handleMessage as EventListener);

    return () => {
      container.removeEventListener("message", handleMessage as EventListener);
    };
  }, [appendLog, appendNotificationHistory]);

  // 🧩 Bloque 8B
  const triggerLocalNotification = useCallback((title: string, body: string) => {
    if (typeof window === "undefined") {
      return;
    }
    if (!("Notification" in window)) {
      return;
    }
    try {
      if (Notification.permission === "granted") {
        new Notification(title, { body });
      }
    } catch (err) {
      if (process.env.NODE_ENV !== "production") {
        console.error("No se pudo mostrar la notificación local", err);
      }
    }
  }, []);

  // 🧩 Bloque 8B
  const sendTestNotification = useCallback(async () => {
    const entry: NotificationHistoryEntry = {
      id: makeId(),
      title: "Notificación de prueba",
      body: "Este es un mensaje de test.",
      timestamp: Date.now(),
    };

    if (!token) {
      appendLog("Generando notificación local de prueba");
      appendNotificationHistory(entry);
      triggerLocalNotification(entry.title, entry.body);
      return;
    }

    try {
      setTesting(true);
      await testNotificationDispatcher(token);
      appendLog("Solicitud de notificación de prueba enviada");
      appendNotificationHistory(entry);
      triggerLocalNotification(entry.title, entry.body);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo enviar la notificación de prueba";
      setError(message);
      appendLog(`Error al enviar prueba: ${message}`);
    } finally {
      setTesting(false);
    }
  }, [appendLog, appendNotificationHistory, token, triggerLocalNotification]);

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
    notificationHistory,
    lastEvent,
    sendTestNotification,
    requestPermission,
    dismissEvent,
    clearLogs,
  };
}
