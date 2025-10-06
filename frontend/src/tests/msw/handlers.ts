import { http, HttpResponse } from "msw";

type PortfolioTestItem = {
  id?: string;
  symbol: string;
  amount: number;
  price?: number | null;
  value?: number | null;
};

interface PortfolioHandlersOptions {
  initialItems?: PortfolioTestItem[];
  defaultPrice?: number;
}

const PORTFOLIO_PATH = "*/api/portfolio";

type MarketKind = "crypto" | "stocks" | "forex";

type Quote = {
  symbol: string;
  price: number;
  raw_change: number;
  source: string;
  type: "crypto" | "stock" | "forex";
};

const NEWS_PATH = "*/api/news/latest";

const MARKET_ENDPOINTS: Record<MarketKind, string> = {
  crypto: "*/api/markets/crypto/prices",
  stocks: "*/api/markets/stocks/quotes",
  forex: "*/api/markets/forex/rates",
};

const MARKET_HISTORY_PATH = "*/api/markets/history/:symbol";

const DEFAULT_QUOTES: Record<MarketKind, Quote> = {
  crypto: {
    symbol: "BTCUSDT",
    price: 50_000,
    raw_change: 2.5,
    source: "Binance",
    type: "crypto",
  },
  stocks: {
    symbol: "AAPL",
    price: 180.5,
    raw_change: 1.1,
    source: "Yahoo Finance",
    type: "stock",
  },
  forex: {
    symbol: "EUR/USD",
    price: 1.08,
    raw_change: 0.2,
    source: "Yahoo Finance",
    type: "forex",
  },
};

const DEFAULT_NEWS = [
  {
    id: "default-1",
    title: "Mercados al alza",
    url: "https://example.com/news",
    source: "Ejemplo",
    summary: "Resumen de prueba",
    published_at: new Date("2024-01-01T00:00:00Z").toISOString(),
  },
];

export const handlers = [
  http.get(NEWS_PATH, () => HttpResponse.json({ articles: DEFAULT_NEWS })),
  http.get(MARKET_ENDPOINTS.crypto, () =>
    HttpResponse.json({ quotes: [DEFAULT_QUOTES.crypto] })
  ),
  http.get(MARKET_ENDPOINTS.stocks, () =>
    HttpResponse.json({ quotes: [DEFAULT_QUOTES.stocks] })
  ),
  http.get(MARKET_ENDPOINTS.forex, () =>
    HttpResponse.json({ quotes: [DEFAULT_QUOTES.forex] })
  ),
  http.get(MARKET_HISTORY_PATH, ({ params }) => {
    const { symbol } = params as { symbol?: string };
    const now = new Date("2024-01-01T00:00:00Z");
    return HttpResponse.json({
      symbol: (symbol as string) ?? "BTCUSDT",
      interval: "1h",
      source: "MockSource",
      values: [
        {
          timestamp: now.toISOString(),
          open: 1,
          high: 1.2,
          low: 0.9,
          close: 1.1,
          volume: 100,
        },
      ],
    });
  }),
  ...createMockPortfolioHandlers(),
  // # QA fix: mock básico del endpoint de chat para suites
  http.post("*/api/chat", () => HttpResponse.json({ messages: [] })),
  // # QA fix: mockear validación de sesión para pruebas
  http.get("*/api/auth/me", () =>
    HttpResponse.json({ user: { id: 1, name: "QA" }, token: "test-token" })
  ),
  // # QA fix: mock de logs de notificaciones
  http.get("*/api/notifications/logs", () => HttpResponse.json([])),
  // # QA fix: mock handshake de realtime websocket
  http.get("*/api/realtime/ws", () => HttpResponse.json({ ok: true })),
  // # QA fix: mock canal de notificaciones websocket
  http.get("*/ws/notifications", () => HttpResponse.json({ ok: true })),
];

export const newsEmptyHandler = http.get(NEWS_PATH, () =>
  HttpResponse.json({ articles: [] }, { status: 200 })
);

export const newsErrorHandler = http.get(
  NEWS_PATH,
  () => new HttpResponse(null, { status: 500 })
);

export const newsTooManyRequestHandler = http.get(
  NEWS_PATH,
  () => new HttpResponse(null, { status: 429 })
);

export const makeMarketQuoteHandler = (
  kind: MarketKind,
  quote: Partial<Quote>
) =>
  http.get(MARKET_ENDPOINTS[kind], () =>
    HttpResponse.json({
      quotes: [
        {
          ...DEFAULT_QUOTES[kind],
          ...quote,
        },
      ],
    })
  );

export const makeMarketEmptyHandler = (kind: MarketKind) =>
  http.get(MARKET_ENDPOINTS[kind], () => HttpResponse.json({ quotes: [] }));

export const makeMarketErrorHandler = (kind: MarketKind) =>
  http.get(MARKET_ENDPOINTS[kind], () => new HttpResponse(null, { status: 500 }));

export const makeMarketRateLimitHandler = (kind: MarketKind) =>
  http.get(
    MARKET_ENDPOINTS[kind],
    () => new HttpResponse(null, { status: 429 })
  );

export const makeHistoricalDataHandler = (response: Record<string, unknown>) =>
  http.get(MARKET_HISTORY_PATH, () => HttpResponse.json(response));

export const makeHistoricalDataErrorHandler = (status = 500) =>
  http.get(MARKET_HISTORY_PATH, () => new HttpResponse(null, { status }));

export function createMockPortfolioHandlers(
  options: PortfolioHandlersOptions = {}
) {
  const defaultPrice = options.defaultPrice ?? 120;
  const provided = options.initialItems ?? [];
  let nextId = 1;
  let items = provided.map((item) => {
    const price = item.price ?? defaultPrice;
    const assignedId = item.id ?? String(nextId);
    nextId += 1;
    const value = item.value ?? price * item.amount;
    return { ...item, id: assignedId, price, value };
  });

  const computeTotal = () =>
    items.reduce((acc, item) => acc + (item.value ?? 0), 0);

  return [
    http.get(PORTFOLIO_PATH, () =>
      HttpResponse.json({
        items,
        total_value: computeTotal(),
      })
    ),
    http.post(PORTFOLIO_PATH, async ({ request }) => {
      const body = await request.json();
      const amount = Number(body?.amount) || 0;
      const price = defaultPrice;
      const newItem = {
        id: String(nextId++),
        symbol: String(body?.symbol ?? "").toUpperCase(),
        amount,
        price,
        value: price * amount,
      };
      items = [...items, newItem];
      return HttpResponse.json(newItem, { status: 201 });
    }),
    http.delete(`${PORTFOLIO_PATH}/:id`, ({ params }) => {
      const id = String((params as { id?: string }).id ?? "");
      items = items.filter((item) => item.id !== id);
      return new HttpResponse(null, { status: 204 });
    }),
  ];
}

export { http, HttpResponse };
