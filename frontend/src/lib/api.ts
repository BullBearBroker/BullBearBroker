export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  name?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type?: string;
  expires_in?: number;
}

export interface UserProfile {
  id: string | number;
  email: string;
  name?: string;
  [key: string]: unknown;
}

export interface MarketQuote {
  symbol: string;
  price: number;
  raw_change?: number | null;
  change?: string | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  source?: string | null;
  type?: "crypto" | "stock" | "forex" | string;
  [key: string]: unknown;
}

export interface MessagePayload {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  messages: MessagePayload[];
  provider?: string;
}

export interface Alert {
  id: string | number;
  title: string;
  condition: string;
  active: boolean;
  created_at?: string;
  [key: string]: unknown;
}

export interface NewsItem {
  id: string | number;
  title: string;
  url: string;
  source?: string;
  published_at?: string;
  summary?: string;
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  withAuthToken?: string | null
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (withAuthToken) {
    headers.set("Authorization", `Bearer ${withAuthToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include"
  });

  if (!response.ok) {
    const message = await safeReadError(response);
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  try {
    return text ? (JSON.parse(text) as T) : (undefined as T);
  } catch (error) {
    throw new Error("Invalid JSON response");
  }
}

async function safeReadError(response: Response) {
  try {
    const data = await response.json();
    if (typeof data === "string") return data;
    if (data?.detail) {
      return typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail);
    }
    if (data?.message) return data.message;
    return JSON.stringify(data);
  } catch {
    return response.statusText;
  }
}

export function login(payload: LoginPayload) {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function register(payload: RegisterPayload) {
  return request<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function refreshToken(refresh_token: string) {
  return request<AuthResponse>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token })
  });
}

export function getProfile(token: string) {
  return request<UserProfile>("/api/auth/me", { method: "GET" }, token);
}

export async function getMarketQuote(
  type: "crypto" | "stock" | "forex",
  symbol: string,
  token?: string
) {
  const normalizedSymbol = symbol.trim().toUpperCase();
  const encodedSymbol = encodeURIComponent(normalizedSymbol);
  let path: string;

  switch (type) {
    case "crypto":
      path = `/api/markets/crypto/prices?symbols=${encodedSymbol}`;
      break;
    case "stock":
      path = `/api/markets/stocks/quotes?symbols=${encodedSymbol}`;
      break;
    case "forex":
      path = `/api/markets/forex/rates?pairs=${encodedSymbol}`;
      break;
    default:
      throw new Error(`Tipo de mercado no soportado: ${type}`);
  }

  const payload = await request<{ quotes: MarketQuote[]; missing?: string[] }>(
    path,
    { method: "GET" },
    token
  );

  const firstQuote = payload.quotes?.[0];
  if (firstQuote) {
    return firstQuote;
  }

  throw new Error(`No se encontró información para ${normalizedSymbol}`);
}

export async function sendChatMessage(
  messages: MessagePayload[],
  token?: string,
  onStreamChunk?: (partial: string) => void
): Promise<ChatResponse> {
  const body = {
    prompt: messages[messages.length - 1]?.content ?? "",
    context: {
      history: messages.slice(0, -1)
    }
  };

  const payload = await request<{ response: string; provider?: string }>(
    "/api/ai/chat",
    {
      method: "POST",
      body: JSON.stringify(body)
    },
    token
  );

  const assistantMessage: MessagePayload = {
    role: "assistant",
    content: payload.response
  };

  const updated = [...messages, assistantMessage];
  if (payload.response && onStreamChunk) {
    onStreamChunk(payload.response);
  }

  return {
    messages: updated,
    provider: payload.provider
  } satisfies ChatResponse;
}

export function listAlerts(token: string) {
  return request<Alert[]>("/api/alerts", { method: "GET" }, token);
}

export function createAlert(token: string, payload: Partial<Alert>) {
  return request<Alert>(
    "/api/alerts",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function updateAlert(
  token: string,
  id: string | number,
  payload: Partial<Alert>
) {
  return request<Alert>(
    `/api/alerts/${id}`,
    {
      method: "PUT",
      body: JSON.stringify(payload)
    },
    token
  );
}

export function deleteAlert(token: string, id: string | number) {
  return request<void>(
    `/api/alerts/${id}`,
    {
      method: "DELETE"
    },
    token
  );
}

export function sendAlertNotification(
  token: string,
  payload: { message: string; telegram_chat_id?: string; discord_channel_id?: string }
) {
  return request<Record<string, { status: string; target: string; error?: string }>>(
    "/api/alerts/send",
    {
      method: "POST",
      body: JSON.stringify(payload)
    },
    token
  );
}

export async function listNews(token?: string) {
  const payload = await request<{ articles: NewsItem[] }>(
    "/api/news/latest",
    { method: "GET" },
    token
  );

  return (
    payload.articles?.map((article, index) => ({
      ...article,
      id: article.id ?? `latest-${index}`,
      source: article.source ?? "Desconocida"
    })) ?? []
  );
}

