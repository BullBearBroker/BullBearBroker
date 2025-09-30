import {
  makeMarketRateLimitHandler,
  createMockPortfolioHandlers,
  newsTooManyRequestHandler,
} from "@/tests/msw/handlers";

describe("MSW handler helpers", () => {
  it("retorna 429 para rate limit en mercados", async () => {
    const handler = makeMarketRateLimitHandler("crypto");
    const response = await handler.resolver(
      { request: new Request("https://example.com/api/markets/crypto/prices") } as any,
      undefined as any,
      undefined as any
    );

    expect(response?.status).toBe(429);
  });

  it("retorna 429 cuando noticias están limitadas", async () => {
    const response = await newsTooManyRequestHandler.resolver(
      { request: new Request("https://example.com/api/news/latest") } as any,
      undefined as any,
      undefined as any
    );

    expect(response?.status).toBe(429);
  });

  it("gestiona flujo básico de portafolio", async () => {
    const [getHandler, postHandler, deleteHandler] = createMockPortfolioHandlers({
      initialItems: [{ symbol: "ETHUSDT", amount: 1.5 }],
      defaultPrice: 200,
    });

    const initial = await getHandler.resolver(
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any
    );
    expect(await initial?.json()).toMatchObject({ total_value: 300 });

    await postHandler.resolver(
      {
        request: new Request("https://example.com/api/portfolio", {
          method: "POST",
          body: JSON.stringify({ symbol: "aapl", amount: 2 }),
        }),
      } as any,
      undefined as any,
      undefined as any
    );

    const afterAdd = await getHandler.resolver(
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any
    );
    const payload = await afterAdd?.json();
    expect(payload.items).toHaveLength(2);
    expect(payload.total_value).toBe(700);

    await deleteHandler.resolver(
      { params: { id: payload.items[0].id }, request: new Request("https://example.com/api/portfolio/1", { method: "DELETE" }) } as any,
      undefined as any,
      undefined as any
    );

    const afterDelete = await getHandler.resolver(
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any
    );
    const finalPayload = await afterDelete?.json();
    expect(finalPayload.items).toHaveLength(1);
    expect(finalPayload.total_value).toBe(400);

    const [emptyGet, emptyPost, emptyDelete] = createMockPortfolioHandlers();

    const emptyResponse = await emptyGet.resolver(
      { request: new Request("https://example.com/api/portfolio") } as any,
      undefined as any,
      undefined as any
    );
    expect(await emptyResponse?.json()).toEqual({ items: [], total_value: 0 });

    await emptyPost.resolver(
      {
        request: new Request("https://example.com/api/portfolio", {
          method: "POST",
          body: JSON.stringify({ amount: "invalid" }),
        }),
      } as any,
      undefined as any,
      undefined as any
    );

    await emptyDelete.resolver(
      { params: {}, request: new Request("https://example.com/api/portfolio/x", { method: "DELETE" }) } as any,
      undefined as any,
      undefined as any
    );
  });
});
