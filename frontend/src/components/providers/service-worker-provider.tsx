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

    let cancelled = false;

    const registerServiceWorker = async () => {
      try {
        const existing = await navigator.serviceWorker.getRegistration(SERVICE_WORKER_PATH);
        const registration =
          existing ?? (await navigator.serviceWorker.register(SERVICE_WORKER_PATH));

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

    registerServiceWorker();

    return () => {
      cancelled = true;
    };
  }, []);

  return null;
}
