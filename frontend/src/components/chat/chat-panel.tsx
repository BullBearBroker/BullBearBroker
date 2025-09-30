"use client";

import React, { FormEvent, useRef, useState } from "react";
import { SendHorizontal } from "lucide-react";

import {
  MessagePayload,
  sendChatMessage
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

interface ChatPanelProps {
  token?: string;
}

const SOURCE_LABELS: Record<string, string> = {
  prices: "Precios", // [Codex] nuevo - etiqueta humana para precios
  indicators: "Indicadores", // [Codex] nuevo
  news: "Noticias", // [Codex] nuevo
  alerts: "Alertas", // [Codex] nuevo
};

export function ChatPanel({ token }: ChatPanelProps) {
  const [messages, setMessages] = React.useState<MessagePayload[]>([
    {
      role: "assistant",
      content:
        "Hola, soy tu asistente financiero BullBear. ¿En qué puedo ayudarte hoy?"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [sources, setSources] = useState<string[]>([]); // [Codex] nuevo - fuentes de datos reales
  const [usedData, setUsedData] = useState(false); // [Codex] nuevo - bandera de datos reales

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!input.trim()) return;
    setError(null);
    const userMessage: MessagePayload = { role: "user", content: input.trim() };
    const pendingConversation = [...messages, userMessage];
    const scrollToEnd = () => {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    setMessages(pendingConversation);
    setInput("");
    setLoading(true);
    scrollToEnd();
    try {
      const response = await sendChatMessage(pendingConversation, token);
      if (response.messages?.length) {
        setMessages(response.messages);
      }
      setSources(response.sources ?? []); // [Codex] nuevo - persistimos fuentes
      setUsedData(Boolean(response.used_data)); // [Codex] nuevo
      scrollToEnd();
    } catch (err) {
      console.error(err);
      setError(
        err instanceof Error
          ? err.message
          : "No se pudo enviar el mensaje. Inténtalo de nuevo."
      );
      setMessages(pendingConversation);
      setSources([]); // [Codex] nuevo - limpiar fuentes ante error
      setUsedData(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Chat con IA</h2>
        {sources.length ? (
          <Badge variant="default">
            {`Respuesta con datos reales (${sources
              .map((source) => SOURCE_LABELS[source] ?? source)
              .join(", ")})`}
          </Badge>
        ) : (
          <Badge variant="secondary">{usedData ? "Datos reales" : "IA"}</Badge>
        )}
      </div>
      <ScrollArea className="flex-1 rounded-lg border">
        <div className="space-y-4 p-4">
          {messages.map((message, index) => (
            <div
              key={`${message.role}-${index}`}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-xl rounded-lg px-4 py-2 text-sm shadow-sm ${
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground"
                }`}
              >
                {message.content}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </ScrollArea>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-2">
        <Textarea
          placeholder="Escribe tu consulta sobre mercados, trading o inversiones..."
          value={input}
          onChange={(event) => setInput(event.target.value)}
          disabled={loading}
        />
        <Button type="submit" className="w-full" disabled={loading}>
          <SendHorizontal className="mr-2 h-4 w-4" />
          {loading ? "Enviando..." : "Enviar"}
        </Button>
      </form>
    </div>
  );
}
