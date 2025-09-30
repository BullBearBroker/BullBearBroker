const envApiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;

if (!envApiUrl) {
  throw new Error("NEXT_PUBLIC_API_URL is not defined");
}

export const API_BASE_URL = envApiUrl.replace(/\/$/, "");

export function resolveWebSocketUrl(path: string): string {
  const base = new URL(API_BASE_URL);
  const wsProtocol = base.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = new URL(path, base);
  wsUrl.protocol = wsProtocol;
  return wsUrl.toString();
}

export function getAlertsWebSocketUrl(token?: string | null): string {
  const url = new URL(resolveWebSocketUrl("/ws/alerts"));
  if (token) {
    url.searchParams.set("token", token);
  }
  return url.toString();
}

/* ===========
   INTERFACES
   =========== */

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  name?: string;
  risk_profile?: "conservador" | "moderado" | "agresivo"; // [Codex] nuevo
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
  used_data?: boolean; // [Codex] nuevo - refleja si hubo datos reales
  sources?: string[]; // [Codex] nuevo - fuentes utilizadas por la IA
  sessionId?: string;
}

export interface ChatHistoryMessage extends MessagePayload {
  id: string;
  created_at: string;
}

export interface ChatHistory {
  session_id: string;
  created_at: string;
  messages: ChatHistoryMessage[];
}

export interface Alert {
  id: string | number;
  title: string;
  asset: string;
  condition: string;
  value: number;
  active: boolean;
  created_at?: string;
  updated_at?: string;
  [key: string]: unknown;
}

export interface PortfolioItem {
  id: string;
  symbol: string;
  amount: number;
  price?: number | null;
  value?: number | null;
}

export interface PortfolioSummary {
  items: PortfolioItem[];
  total_value: number;
}

export interface NewsItem {
  id: string | number;
  title: string;
  url: string;
  source?: string;
  published_at?: string;
  summary?: string;
}

export interface HistoricalCandle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface HistoricalDataResponse {
  symbol: string;
  interval: string;
  source?: string;
  values: HistoricalCandle[];
}

/* ===========
   CORE REQUEST
   =========== */

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
    credentials: "include",
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
  } catch (err) {
    console.error("JSON parse error:", err);
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

/* ===========
   AUTH
   =========== */

export function login(payload: LoginPayload) {
  return request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function register(payload: RegisterPayload) {
  return request<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refreshToken(refresh_token: string) {
  return request<AuthResponse>("/api/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token }),
  });
}

export interface HistoricalQuery {
  interval?: string;
  limit?: number;
  market?: "auto" | "crypto" | "stock" | "equity" | "forex";
}

export function getHistoricalData(
  symbol: string,
  params: HistoricalQuery = {},
  token?: string | null
) {
  const searchParams = new URLSearchParams();
  if (params.interval) {
    searchParams.set("interval", params.interval);
  }
  if (typeof params.limit === "number") {
    searchParams.set("limit", params.limit.toString());
  }
  if (params.market) {
    searchParams.set("market", params.market);
  }

  const query = searchParams.toString();
  const path = `/api/markets/history/${encodeURIComponent(symbol)}${
    query ? `?${query}` : ""
  }`;

  return request<HistoricalDataResponse>(path, {}, token ?? undefined);
}

export function getProfile(token: string) {
  return request<UserProfile>("/api/auth/me", { method: "GET" }, token);
}

/* ===========
   MARKETS
   =========== */

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

/* ===========
   CHAT AI (ahora con indicadores)
   =========== */

export async function sendChatMessage(
  messages: MessagePayload[],
  token?: string,
  onStreamChunk?: (partial: string) => void,
  options?: { symbol?: string; interval?: "1h" | "4h" | "1d"; sessionId?: string }
): Promise<ChatResponse> {
  // 🔹 Obtener indicadores si hay símbolo
  let indicators: any = null;
  if (options?.symbol) {
    try {
      indicators = await getIndicators(
        "crypto",
        options.symbol,
        options.interval || "1h",
        token
      );
    } catch (err) {
      console.warn("No se pudieron obtener indicadores:", err);
    }
  }

  const body: Record<string, unknown> = {
    prompt: messages[messages.length - 1]?.content ?? "",
    context: {
      history: messages.slice(0, -1),
      indicators, // 👈 ahora la IA recibe indicadores técnicos
    },
  };

  if (options?.sessionId) {
    body.session_id = options.sessionId;
  }

  const payload = await request<{
    response: string;
    provider?: string;
    used_data?: boolean;
    sources?: string[];
    session_id?: string;
  }>(
    "/api/ai/chat",
    {
      method: "POST",
      body: JSON.stringify(body),
    },
    token
  );

  const assistantMessage: MessagePayload = {
    role: "assistant",
    content: payload.response,
  };

  const updated = [...messages, assistantMessage];

  if (payload.response && onStreamChunk) {
    onStreamChunk(payload.response);
  }

  return {
    messages: updated,
    provider: payload.provider,
    used_data: payload.used_data,
    sources: payload.sources,
    sessionId: payload.session_id ?? options?.sessionId,
  };
}

export function getChatHistory(sessionId: string, token: string) {
  return request<ChatHistory>(`/api/ai/history/${sessionId}`, { method: "GET" }, token);
}

/* ===========
   ALERTS
   =========== */

export function listAlerts(token: string) {
  return request<Alert[]>("/api/alerts", { method: "GET" }, token);
}

export function createAlert(
  token: string,
  payload: {
    title: string;
    asset: string;
    condition: string;
    value: number;
    active: boolean;
  }
) {
  return request<Alert>(
    "/api/alerts",
    {
      method: "POST",
      body: JSON.stringify(payload),
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
      body: JSON.stringify(payload),
    },
    token
  );
}

/* ===========
   PUSH NOTIFICATIONS
   =========== */

export interface PushSubscriptionPayload {
  endpoint: string;
  keys: {
    auth: string;
    p256dh: string;
  };
}

export interface PushSubscriptionResponse {
  id: string;
}

export function subscribePush(
  payload: PushSubscriptionPayload,
  token: string
) {
  return request<PushSubscriptionResponse>(
    "/api/push/subscribe",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export function sendTestPush(token: string) {
  return request<{ delivered: number }>(
    "/api/push/send-test",
    { method: "POST" },
    token
  );
}

export function deleteAlert(token: string, id: string | number) {
  return request<void>(
    `/api/alerts/${id}`,
    {
      method: "DELETE",
    },
    token
  );
}

export function sendAlertNotification(
  token: string,
  payload: {
    message: string;
    telegram_chat_id?: string;
    discord_channel_id?: string;
  }
) {
  return request<
    Record<string, { status: string; target: string; error?: string }>
  >(
    "/api/alerts/send",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export function suggestAlertCondition(
  token: string,
  payload: { asset: string; interval?: "1h" | "4h" | "1d" }
) {
  // [Codex] nuevo - endpoint para sugerencias impulsadas por IA
  return request<{ suggestion: string; notes?: string }>(
    "/api/alerts/suggest",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

/* ===========
   PORTFOLIO
   =========== */

export function listPortfolio(token: string) {
  return request<PortfolioSummary>("/api/portfolio", { method: "GET" }, token);
}

export function createPortfolioItem(
  token: string,
  payload: { symbol: string; amount: number }
) {
  return request<PortfolioItem>(
    "/api/portfolio",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    token
  );
}

export function deletePortfolioItem(token: string, id: string | number) {
  return request<void>(
    `/api/portfolio/${id}`,
    {
      method: "DELETE",
    },
    token
  );
}

/* ===========
   NEWS
   =========== */

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
      source: article.source ?? "Desconocida",
    })) ?? []
  );
}

/* ===========
   INDICATORS
   =========== */

export async function getIndicators(
  type: "crypto" | "stock" | "forex",
  symbol: string,
  interval: "1h" | "4h" | "1d" = "1h",
  token?: string,
  options?: {
    includeAtr?: boolean;
    includeStochRsi?: boolean;
    includeIchimoku?: boolean;
    includeVwap?: boolean;
  }
) {
  const query = new URLSearchParams({
    type,
    symbol,
    interval,
    include_atr: (options?.includeAtr ?? true).toString(), // [Codex] cambiado - activamos indicadores avanzados
    include_stoch_rsi: (options?.includeStochRsi ?? true).toString(),
    include_ichimoku: (options?.includeIchimoku ?? true).toString(),
    include_vwap: (options?.includeVwap ?? true).toString(),
  });

  return request<{
    symbol: string;
    type: string;
    interval: string;
    count: number;
    source?: string;
    indicators: Record<string, any>;
    series?: {
      closes?: number[];
      highs?: number[];
      lows?: number[];
      volumes?: number[];
    };
  }>(`/api/markets/indicators?${query.toString()}`, { method: "GET" }, token);
}
