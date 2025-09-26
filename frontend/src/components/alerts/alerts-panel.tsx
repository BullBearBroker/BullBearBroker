"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";
import { AlertTriangle, PlusCircle, Trash2 } from "lucide-react";

import {
  Alert,
  createAlert,
  deleteAlert,
  listAlerts,
  sendAlertNotification,
  updateAlert
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface AlertsPanelProps {
  token?: string;
}

export function AlertsPanel({ token }: AlertsPanelProps) {
  const { data, error, mutate, isLoading } = useSWR<Alert[]>(
    token ? ["alerts", token] : null,
    () => listAlerts(token!)
  );

  const [title, setTitle] = useState("");
  const [condition, setCondition] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [dispatchMessage, setDispatchMessage] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [discordChannelId, setDiscordChannelId] = useState("");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchFeedback, setDispatchFeedback] = useState<string | null>(null);
  const [dispatchError, setDispatchError] = useState<string | null>(null);

  const handleCreate = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;
      if (!title.trim() || !condition.trim()) {
        setFormError("Completa el título y la condición de la alerta.");
        return;
      }
      setFormError(null);
      setSubmitting(true);
      try {
        await createAlert(token, {
          title: title.trim(),
          condition: condition.trim(),
          active: true
        });
        setTitle("");
        setCondition("");
        await mutate();
      } catch (err) {
        console.error(err);
        setFormError(
          err instanceof Error
            ? err.message
            : "No se pudo crear la alerta. Inténtalo de nuevo."
        );
      } finally {
        setSubmitting(false);
      }
    },
    [condition, mutate, title, token]
  );

  const toggleAlert = useCallback(
    async (alert: Alert) => {
      if (!token) return;
      try {
        await updateAlert(token, alert.id, { active: !alert.active });
        await mutate();
      } catch (err) {
        console.error(err);
        setFormError(
          err instanceof Error
            ? err.message
            : "No se pudo actualizar la alerta."
        );
      }
    },
    [mutate, token]
  );

  const removeAlert = useCallback(
    async (alert: Alert) => {
      if (!token) return;
      try {
        await deleteAlert(token, alert.id);
        await mutate();
      } catch (err) {
        console.error(err);
        setFormError(
          err instanceof Error
            ? err.message
            : "No se pudo eliminar la alerta."
        );
      }
    },
    [mutate, token]
  );

  const handleSendNotification = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;
      if (!dispatchMessage.trim()) {
        setDispatchError("Escribe un mensaje para enviar la alerta.");
        return;
      }

      setDispatchError(null);
      setDispatchFeedback(null);
      setDispatching(true);
      try {
        const result = await sendAlertNotification(token, {
          message: dispatchMessage.trim(),
          telegram_chat_id: telegramChatId.trim() || undefined,
          discord_channel_id: discordChannelId.trim() || undefined
        });
        const summary = Object.entries(result)
          .map(([channel, payload]) => `${channel}: ${payload.status}`)
          .join(" | ");
        setDispatchFeedback(`Notificación enviada (${summary}).`);
        setDispatchMessage("");
      } catch (err) {
        console.error(err);
        setDispatchError(
          err instanceof Error
            ? err.message
            : "No se pudo enviar la notificación."
        );
      } finally {
        setDispatching(false);
      }
    },
    [discordChannelId, dispatchMessage, telegramChatId, token]
  );

  return (
    <Card className="flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-lg font-medium">Alertas personalizadas</CardTitle>
        <Badge variant="secondary" className="flex items-center gap-1">
          <AlertTriangle className="h-3.5 w-3.5" />
          Activas
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={handleCreate} className="space-y-3">
          <Input
            placeholder="Título de la alerta"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={!token || submitting}
          />
          <Textarea
            placeholder="Condición (ej. BTC > 50,000 USD)"
            value={condition}
            onChange={(event) => setCondition(event.target.value)}
            disabled={!token || submitting}
          />
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <Button type="submit" disabled={!token || submitting} className="w-full">
            <PlusCircle className="mr-2 h-4 w-4" />
            {submitting ? "Creando..." : "Crear alerta"}
          </Button>
        </form>
        <form onSubmit={handleSendNotification} className="space-y-3 rounded-lg border p-3">
          <p className="text-sm font-medium">Enviar alerta manual</p>
          <Textarea
            placeholder="Mensaje para Telegram/Discord"
            value={dispatchMessage}
            onChange={(event) => setDispatchMessage(event.target.value)}
            disabled={!token || dispatching}
          />
          <div className="grid gap-2 md:grid-cols-2">
            <Input
              placeholder="Chat ID de Telegram (opcional)"
              value={telegramChatId}
              onChange={(event) => setTelegramChatId(event.target.value)}
              disabled={!token || dispatching}
            />
            <Input
              placeholder="Canal de Discord (opcional)"
              value={discordChannelId}
              onChange={(event) => setDiscordChannelId(event.target.value)}
              disabled={!token || dispatching}
            />
          </div>
          {dispatchError && <p className="text-xs text-destructive">{dispatchError}</p>}
          {dispatchFeedback && <p className="text-xs text-emerald-600">{dispatchFeedback}</p>}
          <Button type="submit" variant="secondary" disabled={!token || dispatching} className="w-full">
            {dispatching ? "Enviando..." : "Enviar notificación"}
          </Button>
        </form>
        <div className="space-y-3">
          {isLoading && <p className="text-sm text-muted-foreground">Cargando alertas...</p>}
          {error && (
            <p className="text-sm text-destructive">Error al cargar alertas: {error.message}</p>
          )}
          {!isLoading && !error && !data?.length && (
            <p className="text-sm text-muted-foreground">
              Aún no tienes alertas. Crea una para recibir notificaciones.
            </p>
          )}
          {data?.map((alert) => (
            <div
              key={alert.id}
              className="flex items-start justify-between rounded-lg border p-3 text-sm"
            >
              <div className="space-y-1">
                <p className="font-medium">{alert.title}</p>
                <p className="text-muted-foreground">{alert.condition}</p>
                <Badge variant={alert.active ? "default" : "secondary"}>
                  {alert.active ? "Activa" : "Pausada"}
                </Badge>
              </div>
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => toggleAlert(alert)}
                  disabled={!token}
                >
                  {alert.active ? "Pausar" : "Reactivar"}
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  size="icon"
                  onClick={() => removeAlert(alert)}
                  disabled={!token}
                  aria-label="Eliminar alerta"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
