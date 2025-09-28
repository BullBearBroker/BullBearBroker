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
  suggestAlertCondition, // [Codex] nuevo
  updateAlert,
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
  const [asset, setAsset] = useState("");
  const [condition, setCondition] = useState("");
  const [value, setValue] = useState<number | "">("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [dispatchMessage, setDispatchMessage] = useState("");
  const [telegramChatId, setTelegramChatId] = useState("");
  const [discordChannelId, setDiscordChannelId] = useState("");
  const [dispatching, setDispatching] = useState(false);
  const [dispatchFeedback, setDispatchFeedback] = useState<string | null>(null);
  const [dispatchError, setDispatchError] = useState<string | null>(null);
  const [suggesting, setSuggesting] = useState(false); // [Codex] nuevo
  const [suggestError, setSuggestError] = useState<string | null>(null); // [Codex] nuevo
  const [suggestNote, setSuggestNote] = useState<string | null>(null); // [Codex] nuevo

  const quickConditionPresets: { label: string; value: string }[] = [
    { label: "Menor que", value: "<" },
    { label: "Mayor que", value: ">" },
    { label: "Igual a", value: "==" },
  ];

  const handleQuickCondition = useCallback((presetValue: string) => {
    setCondition((prev) => (prev.trim().length === 0 ? presetValue : prev));
  }, []);

  // Crear alerta nueva
  const handleCreate = useCallback(
    async (event: React.FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      if (!token) return;

      if (!title.trim()) {
        setFormError("Debes asignar un título a la alerta.");
        return;
      }

      if (!condition.trim()) {
        setFormError("Debes especificar una condición para la alerta.");
        return;
      }

      if (value === "") {
        setFormError("Debes indicar un valor numérico para la alerta.");
        return;
      }

      if (Number.isNaN(Number(value))) {
        setFormError("El valor debe ser numérico.");
        return;
      }

      setFormError(null);
      setSubmitting(true);
      try {
        const payload = {
          title: title.trim(),
          asset: asset.trim().toUpperCase(),
          condition: condition.trim(),
          value: typeof value === "number" ? value : Number(value),
          active: true,
        };

        if (!payload.asset) {
          setFormError("Debes indicar el activo para la alerta.");
          return;
        }

        await createAlert(token, payload);
        setTitle("");
        setAsset("");
        setCondition("");
        setValue("");
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
    [asset, condition, mutate, title, token, value]
  );

  // Alternar activa/pausada
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

  const handleSuggest = useCallback(async () => {
    if (!token) return;
    if (!asset.trim()) {
      setSuggestError("Completa el campo de activo antes de pedir sugerencias.");
      return;
    }
    setSuggestError(null);
    setSuggestNote(null);
    setSuggesting(true);
    try {
      const response = await suggestAlertCondition(token, {
        asset: asset.trim(),
        interval: "1h",
      });
        setCondition(response.suggestion ?? "");
      setSuggestNote(response.notes ?? null);
    } catch (err) {
      console.error(err);
      setSuggestError(
        err instanceof Error
          ? err.message
          : "No se pudo obtener la sugerencia de la IA."
      );
    } finally {
      setSuggesting(false);
    }
  }, [asset, token]);

  // Eliminar alerta
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

  // Enviar notificación manual
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
          discord_channel_id: discordChannelId.trim() || undefined,
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
        <CardTitle className="text-lg font-medium">
          Alertas personalizadas
        </CardTitle>
        <Badge variant="secondary" className="flex items-center gap-1">
          <AlertTriangle className="h-3.5 w-3.5" />
          Activas
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Formulario: Crear alerta */}
        <form onSubmit={handleCreate} className="space-y-3">
          <Input
            placeholder="Título de la alerta"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            disabled={!token || submitting}
          />
          <Input
            placeholder="Activo (ej. BTCUSDT, AAPL)"
            value={asset}
            onChange={(event) => setAsset(event.target.value)}
            disabled={!token || submitting}
          />
          <Textarea
            placeholder="Condición (ej. BTC > 50,000 USD)"
            value={condition}
            onChange={(event) => setCondition(event.target.value)}
            disabled={!token || submitting}
          />
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>Atajos:</span>
            {quickConditionPresets.map((preset) => (
              <Button
                key={preset.value}
                type="button"
                size="sm"
                variant="outline"
                disabled={!token || submitting || Boolean(condition.trim())}
                onClick={() => handleQuickCondition(preset.value)}
              >
                {preset.label}
                <span className="ml-1 font-mono">{preset.value}</span>
              </Button>
            ))}
          </div>
          <Input
            type="number"
            placeholder="Valor (ej. 30)"
            value={value === "" ? "" : value}
            onChange={(event) =>
              setValue(event.target.value === "" ? "" : Number(event.target.value))
            }
            disabled={!token || submitting}
          />
          <div className="flex items-center justify-between gap-2">
            {suggestError && (
              <p className="text-sm text-destructive">{suggestError}</p>
            )}
            <Button
              type="button"
              variant="secondary"
              onClick={handleSuggest}
              disabled={!token || suggesting}
            >
              ✨ {suggesting ? "Consultando..." : "Sugerir alerta con AI"}
            </Button>
          </div>
          {suggestNote && (
            <p className="text-xs text-muted-foreground">{suggestNote}</p>
          )}
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <Button type="submit" disabled={!token || submitting} className="w-full">
            <PlusCircle className="mr-2 h-4 w-4" />
            {submitting ? "Creando..." : "Crear alerta"}
          </Button>
        </form>

        {/* Formulario: Enviar notificación manual */}
        <form
          onSubmit={handleSendNotification}
          className="space-y-3 rounded-lg border p-3"
        >
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
          {dispatchError && (
            <p className="text-xs text-destructive">{dispatchError}</p>
          )}
          {dispatchFeedback && (
            <p className="text-xs text-emerald-600">{dispatchFeedback}</p>
          )}
          <Button
            type="submit"
            variant="secondary"
            disabled={!token || dispatching}
            className="w-full"
          >
            {dispatching ? "Enviando..." : "Enviar notificación"}
          </Button>
        </form>

        {/* Lista de alertas */}
        <div className="space-y-3">
          {isLoading && (
            <p className="text-sm text-muted-foreground">Cargando alertas...</p>
          )}
          {error && (
            <p className="text-sm text-destructive">
              Error al cargar alertas:{" "}
              {error instanceof Error ? error.message : "Desconocido"}
            </p>
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
                <p className="text-xs text-muted-foreground">
                  {alert.asset} · objetivo {alert.value}
                </p>
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
