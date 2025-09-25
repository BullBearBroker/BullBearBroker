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
  const normalizedSymbol = symbol.trim();
  const path =
    type === "forex"
      ? `/api/markets/forex/${encodeURIComponent(normalizedSymbol)}`
      : `/api/markets/${type}/${encodeURIComponent(normalizedSymbol)}`;

  return request<MarketQuote>(path, { method: "GET" }, token);
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

async function fetchNewsCategory(
  category: string,
  token?: string
): Promise<NewsItem[]> {
  const payload = await request<{ category: string; articles: NewsItem[] }>(
    `/api/news/${category}`,
    { method: "GET" },
    token
  );

  return payload.articles?.map((article, index) => ({
    ...article,
    id: article.id ?? `${category}-${index}`,
    source: article.source ?? category
  })) ?? [];
}

export async function listNews(token?: string) {
  try {
    const direct = await request<NewsItem[] | { articles?: NewsItem[] }>(
      "/api/news",
      { method: "GET" },
      token
    );
    if (Array.isArray(direct)) {
      return direct;
    }
    if (direct?.articles) {
      return direct.articles;
    }
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      console.warn("Falling back to category news endpoints", error);
    }
  }

  const categories = ["crypto", "finance"] as const;
  const results = await Promise.allSettled(categories.map((category) => fetchNewsCategory(category, token)));

  const aggregated: NewsItem[] = [];
  for (const result of results) {
    if (result.status === "fulfilled") {
      aggregated.push(...result.value);
    }
  }

  return aggregated;
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
