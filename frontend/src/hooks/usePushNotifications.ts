"use client";

import { useEffect, useMemo, useState } from "react";

import { subscribePush } from "@/lib/api";

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

interface PushNotificationsState {
  enabled: boolean;
  error: string | null;
  permission: NotificationPermission | "unsupported";
  loading: boolean;
}

export function usePushNotifications(token?: string | null): PushNotificationsState {
  const [enabled, setEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const permission: NotificationPermission | "unsupported" = useMemo(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return "unsupported";
    }
    return Notification.permission;
  }, []);

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
        if (permissionState !== "granted") {
          permissionState = await Notification.requestPermission();
        }
        if (permissionState !== "granted") {
          if (active) {
            setError("Debes habilitar las notificaciones para recibir alertas.");
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
        }
      } catch (err) {
        if (!active) return;
        console.error("No se pudo registrar la suscripción push", err);
        const message =
          err instanceof Error ? err.message : "No se pudo registrar la suscripción push.";
        setError(message);
        setEnabled(false);
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
  }, [token]);

  return { enabled, error, permission, loading };
}
