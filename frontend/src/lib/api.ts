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

export interface MarketEntry {
  symbol: string;
  price: number;
  change_24h?: number;
  [key: string]: unknown;
}

export interface MessagePayload {
  role: "user" | "assistant";
  content: string;
}

export interface ChatResponse {
  messages: MessagePayload[];
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

export function getMarkets(type: "crypto" | "stocks" | "forex", token?: string) {
  return request<MarketEntry[]>(`/api/markets/${type}`, { method: "GET" }, token);
}

export async function sendChatMessage(
  messages: MessagePayload[],
  token?: string,
  onStreamChunk?: (partial: string) => void
): Promise<ChatResponse> {
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}/api/ai`, {
    method: "POST",
    body: JSON.stringify({ messages }),
    headers,
    credentials: "include"
  });

  if (!response.ok) {
    const message = await safeReadError(response);
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  const reader = onStreamChunk ? response.body?.getReader?.() : null;

  if (reader) {
    const decoder = new TextDecoder();
    let aggregated = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      aggregated += decoder.decode(value, { stream: true });
      const partial = sanitizeStreamText(aggregated);
      if (partial.trim()) {
        onStreamChunk?.(partial);
      }
    }

    aggregated += decoder.decode();
    const finalText = sanitizeStreamText(aggregated).trim();
    if (!finalText) {
      return { messages } satisfies ChatResponse;
    }

    try {
      return JSON.parse(finalText) as ChatResponse;
    } catch {
      return {
        messages: [
          ...messages,
          {
            role: "assistant",
            content: finalText
          }
        ]
      } satisfies ChatResponse;
    }
  }

  const text = await response.text();
  if (!text) {
    return { messages } satisfies ChatResponse;
  }

  try {
    return JSON.parse(text) as ChatResponse;
  } catch {
    const cleaned = sanitizeStreamText(text).trim();
    return {
      messages: [
        ...messages,
        {
          role: "assistant",
          content: cleaned || text
        }
      ]
    } satisfies ChatResponse;
  }
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

export function listNews(token?: string) {
  return request<NewsItem[]>("/api/news", { method: "GET" }, token ?? undefined);
}

function sanitizeStreamText(raw: string) {
  if (!raw) return "";
  if (!raw.includes("data:")) {
    return raw;
  }

  return raw
    .split(/\r?\n/)
    .filter((line) => line.trim() && !line.startsWith("event:"))
    .map((line) => (line.startsWith("data:") ? line.replace(/^data:\s*/, "") : line))
    .join("\n");
}
