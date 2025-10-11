"use client";

import { useEffect } from "react";

const SERVICE_WORKER_PATH = "/sw.js";

export function ServiceWorkerProvider() {
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    if (!("serviceWorker" in navigator)) {
      return;
    }

    const serviceWorker = navigator.serviceWorker;
    if (!serviceWorker) {
      return;
    }

    let cancelled = false;

    const registerServiceWorker = async () => {
      try {
        const existing = await serviceWorker.getRegistration(SERVICE_WORKER_PATH);
        const registration = existing ?? (await serviceWorker.register(SERVICE_WORKER_PATH));

        if (cancelled) {
          return;
        }

        if (registration.waiting) {
          registration.waiting.postMessage({ type: "SKIP_WAITING" });
        }
      } catch (error) {
        if (process.env.NODE_ENV !== "production") {
          console.error("Service worker registration failed", error);
        }
      }
    };

    const handleControllerChange = () => {
      if (cancelled) {
        return;
      }
      // ✅ Reintenta el registro cuando cambia el controlador del SW
      void registerServiceWorker();
    };

    serviceWorker.addEventListener?.("controllerchange", handleControllerChange); // 🔧 Vigila actualizaciones del service worker activo
    registerServiceWorker();

    return () => {
      cancelled = true;
      serviceWorker.removeEventListener?.("controllerchange", handleControllerChange); // 🔧 Limpia el listener al desmontar el provider
    };
  }, []);

  return null;
}
