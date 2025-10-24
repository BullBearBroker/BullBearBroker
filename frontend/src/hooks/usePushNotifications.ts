"use client";

// 🧩 Bloque 8B
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  fetchVapidPublicKey,
  subscribePush,
  testNotificationDispatcher,
  unsubscribePush,
} from "@/lib/api";
import { isLikelyVapidPlaceholder, normalizeVapidKey, urlBase64ToUint8Array } from "@/utils/vapid";

const PLACEHOLDER_VAPID_REGEX = /^BB_placeholder|^PLACEHOLDER|^test_/i;

function readVapidEnvValue(): string {
  const raw =
    process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? process.env.NEXT_PUBLIC_VAPID_KEY ?? "";
  return raw.trim();
}

export const PERMISSION_DENIED_MESSAGE = "Debes permitir notificaciones para recibir alertas.";

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

export interface PushNotificationsState {
  enabled: boolean;
  error: string | null;
  isSupported: boolean;
  permission: NotificationPermission | "unsupported";
  loading: boolean;
  testing: boolean;
  events: NotificationEnvelope[];
  logs: string[];
  notificationHistory: NotificationHistoryEntry[];
  lastEvent: NotificationEnvelope | null;
  subscription: PushSubscription | null;
  subscribe: () => Promise<PushSubscription>;
  unsubscribe: () => Promise<boolean>;
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
  vapidPublicKey?: string | null,
): Promise<PushSubscription> {
  const toastApi = (
    globalThis as {
      toast?: { error?: (message: string) => void };
    }
  ).toast;

  let serverKey = normalizeVapidKey(vapidPublicKey);
  if (!serverKey) {
    serverKey = normalizeVapidKey(await fetchVapidPublicKey());
  }

  if (!serverKey) {
    await new Promise((resolve) => setTimeout(resolve, 2000));
    serverKey = normalizeVapidKey(await fetchVapidPublicKey());
  }

  if (!serverKey) {
    if (toastApi?.error) {
      toastApi.error("Faltan claves VAPID");
    }
    throw new Error("Missing VAPID key");
  }

  if (isLikelyVapidPlaceholder(serverKey)) {
    if (toastApi?.error) {
      toastApi.error("Configura una clave pública VAPID real en el entorno");
    }
    throw new Error("Invalid VAPID key");
  }

  const localKey = normalizeVapidKey(readVapidEnvValue()); // QA 2.0: alineado con NEXT_PUBLIC_VAPID_PUBLIC_KEY

  if (localKey && localKey !== serverKey) {
    console.warn("VAPID public key mismatch between frontend and backend.");
  }

  const swContainer = navigator.serviceWorker;
  const swReg =
    registration ??
    ("ready" in swContainer && swContainer.ready ? await swContainer.ready : undefined);

  if (!swReg) {
    throw new Error("Service worker registration unavailable.");
  }

  const existingSubscription = await swReg.pushManager.getSubscription();
  if (existingSubscription) {
    return existingSubscription;
  }

  const applicationServerKey = urlBase64ToUint8Array(serverKey);
  return swReg.pushManager.subscribe({
    applicationServerKey: applicationServerKey as unknown as BufferSource,
    userVisibleOnly: true,
  });
}

export function usePushNotifications(token?: string | null): PushNotificationsState {
  const vapid = useMemo(() => readVapidEnvValue(), []);
  const isPlaceholderVapid = useMemo(
    () => !vapid || PLACEHOLDER_VAPID_REGEX.test(vapid),
    [vapid],
  );
  const swSupported = typeof navigator !== "undefined" && "serviceWorker" in navigator;
  const pushSupported = typeof window !== "undefined" && "PushManager" in window;
  const supportedByBrowser = swSupported && pushSupported;
  const isSupported = supportedByBrowser && !isPlaceholderVapid;

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
  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(() => {
    if (!isSupported) {
      return "unsupported";
    }
    if (typeof window === "undefined" || !("Notification" in window)) {
      return "unsupported";
    }
    return Notification.permission;
  });
  const [subscription, setSubscription] = useState<PushSubscription | null>(null);

  useEffect(() => {
    if (!vapid && typeof console !== "undefined") {
      console.warn("⚠️ Missing VAPID key from environment");
    }
  }, [vapid]);

  useEffect(() => {
    if (!isSupported) {
      setEnabled(false);
      setPermission("unsupported");
    }
  }, [isSupported]);

  const appendLog = useCallback((message: string) => {
    setLogs((prev) => {
      const next = [...prev, `[${nowLabel()}] ${message}`];
      return next.slice(-25);
    });
  }, []);

  // 🧩 Bloque 8B
  const appendNotificationHistory = useCallback((entry: NotificationHistoryEntry) => {
    setNotificationHistory((prev) => {
      const next = [...prev, entry];
      return next.slice(-100);
    });
  }, []);

  const resolveVapidKey = useCallback(async () => {
    const localCandidate = normalizeVapidKey(readVapidEnvValue());

    const fetchCandidate = async () => {
      try {
        return normalizeVapidKey(await fetchVapidPublicKey());
      } catch (error) {
        if (process.env.NODE_ENV !== "production") {
          console.warn("Error fetching VAPID key from backend", error);
        }
        return "";
      }
    };

    let serverKey = await fetchCandidate();
    if (!serverKey && localCandidate) {
      serverKey = localCandidate;
    }

    if (!serverKey) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      serverKey = await fetchCandidate();
      if (!serverKey && localCandidate) {
        serverKey = localCandidate;
      }
    }

    if (!serverKey) {
      throw new Error("No se pudo obtener la clave pública VAPID desde el servidor.");
    }

    if (localCandidate && serverKey !== localCandidate) {
      console.warn("VAPID public key mismatch between frontend y backend.");
      appendLog("Clave VAPID distinta entre frontend y backend");
    }

    if (isLikelyVapidPlaceholder(serverKey)) {
      throw new Error("La clave pública VAPID configurada es un placeholder.");
    }

    return serverKey;
  }, [appendLog]);

  const subscribe = useCallback(async () => {
    if (typeof window === "undefined") {
      throw new Error("Entorno de navegador no disponible");
    }
    if (isPlaceholderVapid) {
      const message = !vapid
        ? "Se requiere una clave pública VAPID válida para habilitar las notificaciones."
        : "La clave pública VAPID configurada es un placeholder.";
      appendLog(message);
      setError(message);
      setEnabled(false);
      setPermission("unsupported");
      throw new Error(message);
    }
    if (!("Notification" in window)) {
      appendLog("Notificaciones push no soportadas en este navegador");
      setPermission("unsupported");
      throw new Error("Las notificaciones push no están soportadas en este navegador.");
    }
    if (!("PushManager" in window)) {
      appendLog("Notificaciones push no soportadas en este navegador");
      setPermission("unsupported");
      throw new Error("Las notificaciones push no están soportadas en este navegador.");
    }
    if (!("serviceWorker" in navigator)) {
      appendLog("Los service workers no están soportados en este navegador");
      setPermission("unsupported");
      throw new Error("Los service workers no están soportados en este navegador.");
    }

    const registration = await navigator.serviceWorker.ready;
    if (!registration) {
      throw new Error("Service worker registration unavailable.");
    }

    let permissionState: NotificationPermission = Notification.permission;
    setPermission(permissionState);

    if (permissionState === "denied") {
      setError(PERMISSION_DENIED_MESSAGE);
      setEnabled(false);
      throw new Error(PERMISSION_DENIED_MESSAGE);
    }

    if (permissionState !== "granted") {
      setError(null);
      const result = await Notification.requestPermission();
      permissionState = result;
      setPermission(permissionState);
      appendLog(
        result === "granted"
          ? "Permiso de notificaciones concedido"
          : result === "denied"
            ? "Permiso de notificaciones denegado"
            : "Permiso de notificaciones pendiente",
      );
      if (permissionState !== "granted") {
        if (permissionState === "denied") {
          setError(PERMISSION_DENIED_MESSAGE);
        }
        setEnabled(false);
        throw new Error(
          permissionState === "denied"
            ? PERMISSION_DENIED_MESSAGE
            : "Permiso de notificaciones pendiente",
        );
      }
    }

    const serverKey = await resolveVapidKey();
    const activeSubscription = await registerPushSubscription(registration, serverKey);
    appendLog("Clave pública VAPID validada correctamente");

    const json = activeSubscription.toJSON();
    const auth = json.keys?.auth ?? "";
    const p256dh = json.keys?.p256dh ?? "";
    const expirationTime =
      typeof activeSubscription.expirationTime === "number"
        ? new Date(activeSubscription.expirationTime).toISOString()
        : null;

    if (token) {
      try {
        await subscribePush(
          {
            endpoint: activeSubscription.endpoint,
            expirationTime,
            keys: { auth, p256dh },
          },
          token,
        );
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "No se pudo registrar la suscripción en el backend.";
        setError(message);
        appendLog(`Error al registrar la suscripción en backend: ${message}`);
        throw err;
      }
    } else {
      appendLog("Suscripción local creada sin token de autenticación");
    }

    setSubscription(activeSubscription);
    setEnabled(isSupported && permissionState === "granted" && Boolean(activeSubscription));
    setError(null);
    appendLog("Suscripción push activa");
    return activeSubscription;
  }, [appendLog, isPlaceholderVapid, isSupported, resolveVapidKey, token, vapid]);

  const unsubscribe = useCallback(async () => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
      appendLog("Service worker no disponible para cancelar la suscripción push");
      return false;
    }
    const registration = await navigator.serviceWorker.ready;
    if (!registration) {
      appendLog("No se encontró un registro de service worker activo");
      return false;
    }
    const currentSubscription = await registration.pushManager.getSubscription();
    if (!currentSubscription) {
      appendLog("No había suscripción push activa");
      return false;
    }
    try {
      await currentSubscription.unsubscribe();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "No se pudo cancelar la suscripción push";
      appendLog(`Error al cancelar la suscripción: ${message}`);
      throw err;
    }

    if (token) {
      const endpoint = currentSubscription.endpoint;
      try {
        await unsubscribePush(endpoint, token);
        appendLog("Suscripción eliminada en backend");
      } catch (err) {
        const message =
          err instanceof Error
            ? err.message
            : "No se pudo eliminar la suscripción en el backend";
        appendLog(`Error al eliminar suscripción en backend: ${message}`);
      }
    }

    setSubscription(null);
    setEnabled(false);
    setError(null);
    return true;
  }, [appendLog, token]);

  const subscribeRef = useRef(subscribe);
  useEffect(() => {
    subscribeRef.current = subscribe;
  }, [subscribe]);

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
    window.localStorage.setItem("notificationHistory", JSON.stringify(notificationHistory));
  }, [notificationHistory]);

  const dismissEvent = useCallback((id: string) => {
    setEvents((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const requestPermission = useCallback(async () => {
    if (isPlaceholderVapid) {
      const message = !vapid
        ? "Se requiere una clave pública VAPID válida para habilitar las notificaciones."
        : "La clave pública VAPID configurada es un placeholder.";
      appendLog(message);
      setError(message);
      setPermission("unsupported");
      return "unsupported";
    }
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
          : "Permiso de notificaciones pendiente",
    );
    if (result === "denied") {
      setError(PERMISSION_DENIED_MESSAGE);
    } else if (result === "granted") {
      setError(null);
    }
    return result;
  }, [appendLog, isPlaceholderVapid, permission, vapid]);

  useEffect(() => {
    if (!token) {
      return;
    }
    let active = true;
    const attemptSubscription = async () => {
      setLoading(true);
      try {
        await subscribe();
      } catch (err) {
        if (!active) {
          return;
        }
        const message =
          err instanceof Error ? err.message : "No se pudo registrar la suscripción push.";
        if (process.env.NODE_ENV !== "production") {
          console.error("No se pudo registrar la suscripción push", err);
        }
        setError(message);
        setEnabled(false);
        setSubscription(null);
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

    void attemptSubscription();

    return () => {
      active = false;
    };
  }, [appendLog, subscribe, token]);

  useEffect(() => {
    if (!token) {
      setEnabled(false);
      setSubscription(null);
    }
  }, [token]);

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
      if (type === "push:subscription-change") {
        appendLog("Cambio de suscripción push detectado – reintentando registro");
        void subscribeRef.current?.().catch((error) => {
          if (process.env.NODE_ENV !== "production") {
            console.warn("Fallo al reintentar suscripción push", error);
          }
        });
        return;
      }
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
  }, [appendLog, appendNotificationHistory, subscribe]);

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
    isSupported,
    permission,
    loading,
    testing,
    events,
    logs,
    notificationHistory,
    lastEvent,
    subscription,
    subscribe,
    unsubscribe,
    sendTestNotification,
    requestPermission,
    dismissEvent,
    clearLogs,
  };
}
