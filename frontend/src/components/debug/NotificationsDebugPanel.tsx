"use client";

// QA: Panel de depuración – Web Push

import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { sendTestPush } from "@/lib/api";
import type { PushNotificationsState } from "@/hooks/usePushNotifications";
import { isLikelyVapidPlaceholder, normalizeVapidKey } from "@/utils/vapid";

const MAX_LOG_ITEMS = 30;

function useLocalLog() {
  const [entries, setEntries] = useState<string[]>([]);

  const append = useCallback((message: string) => {
    setEntries((prev) => {
      const next = [...prev, message];
      return next.slice(-MAX_LOG_ITEMS);
    });
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  return { entries, append, clear };
}

type NotificationsDebugPanelProps = {
  pushState: PushNotificationsState;
  token?: string;
};

export default function NotificationsDebugPanel({ pushState, token }: NotificationsDebugPanelProps) {
  const {
    permission,
    isSupported,
    subscription,
    subscribe,
    unsubscribe,
    requestPermission,
    sendTestNotification,
    logs,
    error,
    enabled,
  } = pushState;

  const [pendingAction, setPendingAction] = useState<"subscribe" | "unsubscribe" | "test" | null>(
    null,
  );
  const { entries: localLogs, append: appendLocalLog } = useLocalLog();

  const vapidKey = useMemo(
    () => normalizeVapidKey(process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY ?? ""),
    [],
  );
  const vapidPlaceholder = isLikelyVapidPlaceholder(vapidKey);
  const disableSubscribe = pendingAction === "subscribe" || !isSupported || vapidPlaceholder;

  useEffect(() => {
    if (vapidPlaceholder) {
      appendLocalLog("⚠️ NEXT_PUBLIC_VAPID_PUBLIC_KEY es un placeholder");
    }
  }, [appendLocalLog, vapidPlaceholder]);

  const handleSubscribe = async () => {
    if (vapidPlaceholder) {
      appendLocalLog("⚠️ Clave VAPID de ejemplo – configura una real antes de suscribirte");
      return;
    }
    setPendingAction("subscribe");
    try {
      const sub = await subscribe();
      appendLocalLog(`✅ Suscripción activa: ${sub.endpoint}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      appendLocalLog(`❌ Error al suscribir: ${message}`);
    } finally {
      setPendingAction(null);
    }
  };

  const handleUnsubscribe = async () => {
    setPendingAction("unsubscribe");
    try {
      const removed = await unsubscribe();
      appendLocalLog(removed ? "✅ Suscripción eliminada" : "ℹ️ No había suscripción activa");
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      appendLocalLog(`❌ Error al desuscribir: ${message}`);
    } finally {
      setPendingAction(null);
    }
  };

  const handleSendTest = async () => {
    if (!token) {
      appendLocalLog("⚠️ Se requiere sesión para enviar pruebas al backend");
      try {
        await sendTestNotification();
        appendLocalLog("ℹ️ Se solicitó una notificación de prueba local");
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        appendLocalLog(`❌ Error al enviar notificación local: ${message}`);
      }
      return;
    }
    setPendingAction("test");
    try {
      const result = await sendTestPush(token);
      appendLocalLog(`🚀 Test push solicitado (entregadas: ${result.delivered ?? 0})`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      appendLocalLog(`❌ Error al solicitar push: ${message}`);
    } finally {
      setPendingAction(null);
    }
  };

  const effectiveLogs = useMemo(() => [...logs, ...localLogs].slice(-MAX_LOG_ITEMS), [logs, localLogs]);

  return (
    <div className="rounded-lg border border-border/60 bg-card p-4">
      <h3 className="text-base font-semibold">Debug Web Push</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Usa este panel para validar el flujo de suscripción, envío y recepción de notificaciones
        Web Push con claves VAPID reales.
      </p>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="font-medium text-muted-foreground">Soporte</dt>
          <dd>{isSupported ? "Sí" : "No"}</dd>
        </div>
        <div>
          <dt className="font-medium text-muted-foreground">Permiso</dt>
          <dd>{permission}</dd>
        </div>
        <div>
          <dt className="font-medium text-muted-foreground">Suscripción</dt>
          <dd>{subscription ? "Activa" : "No"}</dd>
        </div>
        <div>
          <dt className="font-medium text-muted-foreground">Estado backend</dt>
          <dd>{enabled ? "Registrada" : "Sin registrar"}</dd>
        </div>
      </dl>
      {subscription ? (
        <p className="mt-2 break-all text-xs text-muted-foreground">
          Endpoint: {subscription.endpoint}
        </p>
      ) : null}
      {error ? <p className="mt-2 text-sm text-destructive">Error: {error}</p> : null}
      {vapidPlaceholder ? (
        <p className="mt-2 text-sm text-amber-500">
          Configura <code>NEXT_PUBLIC_VAPID_PUBLIC_KEY</code> con una clave pública real para probar
          suscripciones push.
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => void requestPermission()}>
          Solicitar permiso
        </Button>
        <Button
          size="sm"
          onClick={() => void handleSubscribe()}
          disabled={disableSubscribe}
        >
          {pendingAction === "subscribe" ? "Suscribiendo…" : "Suscribirse"}
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => void handleUnsubscribe()}
          disabled={pendingAction === "unsubscribe" || !subscription}
        >
          {pendingAction === "unsubscribe" ? "Eliminando…" : "Desuscribirse"}
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => void handleSendTest()}
          disabled={pendingAction === "test"}
        >
          {pendingAction === "test" ? "Enviando…" : "Enviar test (backend)"}
        </Button>
      </div>
      <div className="mt-4">
        <h4 className="text-sm font-semibold">Logs</h4>
        {effectiveLogs.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sin eventos registrados aún.</p>
        ) : (
          <ul className="mt-1 max-h-40 overflow-auto rounded-md border border-border/40 bg-background/60 p-2 text-xs">
            {effectiveLogs.map((log, index) => (
              <li key={`${log}-${index}`} className="py-0.5">
                {log}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-3 text-xs text-muted-foreground">
        Safari (macOS/iOS) requiere gesto de usuario y sitio HTTPS (o <code>http://localhost</code>)
        para habilitar Web Push.
      </p>
    </div>
  );
}
