import {
  makeMarketRateLimitHandler,
  createMockPortfolioHandlers,
  newsTooManyRequestHandler,
} from "@/tests/msw/handlers";

type ResolverLike = (...args: unknown[]) => unknown;

function executeResolver(handler: unknown, ...args: unknown[]) {
  if (
    handler &&
    typeof handler === "object" &&
    "resolver" in handler &&
    typeof (handler as { resolver?: ResolverLike }).resolver === "function"
  ) {
    return (handler as { resolver: ResolverLike }).resolver(...args);
  }
  throw new Error("Handler does not expose a resolver function");
}

async function readJson(response: unknown) {
  if (!response) {
    return null;
  }
  if (response instanceof Response) {
    return response.json();
  }
  const candidate = response as { json?: () => Promise<unknown> };
  if (typeof candidate.json === "function") {
    return candidate.json();
  }
  throw new Error("Response object does not implement json()");
}

function getStatus(response: unknown): number | undefined {
  if (!response) {
    return undefined;
  }
  if (response instanceof Response) {
    return response.status;
  }
  const candidate = response as { status?: number };
  return typeof candidate.status === "number" ? candidate.status : undefined;
}

describe("MSW handler helpers", () => {
  it("retorna 429 para rate limit en mercados", async () => {
    const handler = makeMarketRateLimitHandler("crypto");
    const response = await executeResolver(
      handler,
      { request: new Request("https://example.com/api/markets/crypto/prices") } as any,
      undefined as any,
      undefined as any,
    );

    expect(getStatus(response)).toBe(429);
  });

  it("retorna 429 cuando noticias están limitadas", async () => {
    const response = await executeResolver(
      newsTooManyRequestHandler,
      { request: new Request("https://example.com/api/news/latest") } as any,
      undefined as any,
      undefined as any,
    );

    expect(getStatus(response)).toBe(429);
  });

  it("gestiona flujo básico de portafolio", async () => {
    const [getHandler, postHandler, deleteHandler] = createMockPortfolioHandlers({
      initialItems: [{ symbol: "ETHUSDT", amount: 1.5 }],
      defaultPrice: 200,
    });

    const initial = await executeResolver(
      getHandler,
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any,
    );
    expect(await readJson(initial)).toMatchObject({ total_value: 300 });

    await executeResolver(
      postHandler,
      {
        request: new Request("https://example.com/api/portfolio", {
          method: "POST",
          body: JSON.stringify({ symbol: "aapl", amount: 2 }),
        }),
      } as any,
      undefined as any,
      undefined as any,
    );

    const afterAdd = await executeResolver(
      getHandler,
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any,
    );
    const payload = (await readJson(afterAdd)) as {
      items: Array<{ id: string }>;
      total_value: number;
    };
    expect(payload.items).toHaveLength(2);
    expect(payload.total_value).toBe(700);

    await executeResolver(
      deleteHandler,
      {
        params: { id: payload.items[0].id },
        request: new Request("https://example.com/api/portfolio/1", { method: "DELETE" }),
      } as any,
      undefined as any,
      undefined as any,
    );

    const afterDelete = await executeResolver(
      getHandler,
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any,
    );
    const finalPayload = (await readJson(afterDelete)) as {
      items: Array<unknown>;
      total_value: number;
    };
    expect(finalPayload.items).toHaveLength(1);
    expect(finalPayload.total_value).toBe(400);

    const [emptyGet, emptyPost, emptyDelete] = createMockPortfolioHandlers();

    const emptyResponse = await executeResolver(
      emptyGet,
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any,
    );
    expect(await readJson(emptyResponse)).toEqual({ items: [], total_value: 0 });

    await executeResolver(
      emptyPost,
      {
        request: new Request("https://example.com/api/portfolio", {
          method: "POST",
          body: JSON.stringify({ amount: "invalid" }),
        }),
      } as any,
      undefined as any,
      undefined as any,
    );

    await executeResolver(
      emptyDelete,
      {
        params: {},
        request: new Request("https://example.com/api/portfolio/x", { method: "DELETE" }),
      } as any,
      undefined as any,
      undefined as any,
    );
  });
});
