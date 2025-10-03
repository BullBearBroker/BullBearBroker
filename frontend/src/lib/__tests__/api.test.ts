import * as api from "../api";

const { request, API_BASE_URL } = api;

describe("request", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    (global.fetch as jest.Mock | undefined)?.mockReset?.();
    global.fetch = originalFetch;
  });

  it("realiza una petición GET con fetch mockeado", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue(JSON.stringify({ result: "ok" })),
      headers: new Headers(),
    });

    const data = await request<{ result: string }>("/demo", { method: "GET" });

    expect(global.fetch).toHaveBeenCalledWith(
      `${API_BASE_URL}/demo`,
      expect.objectContaining({ method: "GET", credentials: "include" })
    );
    expect(data.result).toBe("ok");
  });

  it("envía el body correcto en una petición POST", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue(JSON.stringify({ created: true })),
      headers: new Headers(),
    });

    const payload = { name: "Alert", value: 42 };
    await request("/demo", { method: "POST", body: JSON.stringify(payload) });

    const options = (global.fetch as jest.Mock).mock.calls[0][1];
    expect(options?.method).toBe("POST");
    expect(options?.headers.get("Content-Type")).toBe("application/json");
    expect(options?.body).toBe(JSON.stringify(payload));
  });

  it("soporta peticiones PUT y DELETE", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue(JSON.stringify({ updated: true })),
      headers: new Headers(),
    });

    await request("/demo/1", { method: "PUT", body: JSON.stringify({ status: "active" }) });
    await request("/demo/1", { method: "DELETE" });

    const [putCall, deleteCall] = (global.fetch as jest.Mock).mock.calls;
    expect(putCall[1]?.method).toBe("PUT");
    expect(deleteCall[1]?.method).toBe("DELETE");
  });

  it("lanza un error descriptivo cuando fetch falla", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      json: jest.fn().mockResolvedValue({ detail: "Fallo interno" }),
      statusText: "Internal Server Error",
      text: jest.fn(),
      headers: new Headers(),
    });

    await expect(request("/demo", { method: "GET" })).rejects.toThrow(
      "Internal Server Error"
    );
  });

  it("propaga un error cuando el JSON no es válido", async () => {
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      text: jest.fn().mockResolvedValue("no-json"),
      headers: new Headers(),
    });

    await expect(request("/demo", { method: "GET" })).rejects.toThrow(
      "Invalid JSON response"
    );
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  it("usa el statusText cuando el cuerpo de error no se puede parsear", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 400,
      json: jest.fn().mockRejectedValue(new Error("invalid")),
      statusText: "Bad Request",
      text: jest.fn(),
      headers: new Headers(),
    });

    await expect(request("/demo", { method: "GET" })).rejects.toThrow("Bad Request");
  });

  it("prioriza el campo message cuando está disponible", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 422,
      json: jest.fn().mockResolvedValue({ message: "Mensaje amigable" }),
      statusText: "Unprocessable Entity",
      text: jest.fn(),
      headers: new Headers(),
    });

    await expect(request("/demo", { method: "GET" })).rejects.toThrow(
      "Unprocessable Entity"
    );
  });

  it("serializa el detalle cuando no es un string", async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 409,
      json: jest.fn().mockResolvedValue({ detail: { code: "duplicated" } }),
      statusText: "Conflict",
      text: jest.fn(),
      headers: new Headers(),
    });

    await expect(request("/demo", { method: "GET" })).rejects.toThrow("Conflict");
  });
});

describe("API wrappers", () => {
  const originalFetch = global.fetch;

  function createResponse(data: any, status = 200) {
    return {
      ok: status < 400,
      status,
      statusText: status >= 400 ? "Error" : "OK",
      text: jest.fn().mockResolvedValue(JSON.stringify(data)),
      json: jest.fn().mockResolvedValue(data),
      headers: new Headers(),
    } as any;
  }

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    (global.fetch as jest.Mock).mockReset();
    global.fetch = originalFetch;
  });

  it("llama a los endpoints de autenticación con los datos correctos", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(createResponse({ access_token: "r", refresh_token: "s" }))
      .mockResolvedValueOnce(createResponse({ access_token: "a", refresh_token: "b" }))
      .mockResolvedValueOnce(createResponse({ access_token: "c", refresh_token: "d" }))
      .mockResolvedValueOnce(createResponse({ id: "user" }));

    await api.register({ email: "user@example.com", password: "secret", name: "User" });
    await api.login({ email: "user@example.com", password: "secret" });
    await api.refreshToken("refresh-value");
    await api.getProfile("token-123");

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][0]).toBe(`${API_BASE_URL}/api/auth/register`);
    expect(JSON.parse(calls[0][1].body)).toMatchObject({
      email: "user@example.com",
      name: "User",
    });
    expect(calls[1][0]).toBe(`${API_BASE_URL}/api/auth/login`);
    expect(JSON.parse(calls[1][1].body)).toEqual({
      email: "user@example.com",
      password: "secret",
    });
    expect(calls[2][0]).toBe(`${API_BASE_URL}/api/auth/refresh`);
    expect(JSON.parse(calls[2][1].body)).toEqual({ refresh_token: "refresh-value" });
    expect(calls[3][0]).toBe(`${API_BASE_URL}/api/auth/me`);
    expect((calls[3][1].headers as Headers).get("Authorization")).toBe(
      "Bearer token-123"
    );
  });

  it("administra operaciones CRUD de alertas", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(createResponse([{ id: "1" }]))
      .mockResolvedValueOnce(
        createResponse({ id: "2", title: "Alerta", active: true })
      )
      .mockResolvedValueOnce(createResponse({ id: "3", active: false }))
      .mockResolvedValueOnce({
        ok: true,
        status: 204,
        statusText: "No Content",
        text: jest.fn().mockResolvedValue(""),
        headers: new Headers(),
      });

    await api.listAlerts("token");
    await api.createAlert("token", {
      title: "Alerta",
      asset: "BTC",
      condition: "> 40000",
      value: 40000,
      active: true,
    });
    await api.updateAlert("token", "1", { active: false });
    await api.deleteAlert("token", "2");

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][0]).toBe(`${API_BASE_URL}/api/alerts`);
    expect(calls[1][0]).toBe(`${API_BASE_URL}/api/alerts`);
    expect(JSON.parse(calls[1][1].body)).toMatchObject({ title: "Alerta" });
    expect(calls[2][0]).toBe(`${API_BASE_URL}/api/alerts/1`);
    expect(JSON.parse(calls[2][1].body)).toEqual({ active: false });
    expect(calls[3][0]).toBe(`${API_BASE_URL}/api/alerts/2`);
    expect(calls[3][1].method).toBe("DELETE");
  });

  it("envía notificaciones y solicita sugerencias de alertas", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(createResponse({ status: "ok" }))
      .mockResolvedValueOnce(createResponse({ suggestion: "Comprar" }));

    await api.sendAlertNotification("token", { message: "Hola" });
    await api.suggestAlertCondition("token", { asset: "BTC" });

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][0]).toBe(`${API_BASE_URL}/api/alerts/send`);
    expect(JSON.parse(calls[0][1].body)).toEqual({ message: "Hola" });
    expect(calls[1][0]).toBe(`${API_BASE_URL}/api/alerts/suggest`);
    expect(JSON.parse(calls[1][1].body)).toEqual({ asset: "BTC" });
  });

  it("consulta noticias e indicadores con parámetros personalizados", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(createResponse({ articles: [] }))
      .mockResolvedValueOnce(createResponse({ indicators: { rsi: 55 } }));

    await api.listNews("token");
    await api.getIndicators("crypto", "BTCUSDT", "4h", "token", {
      includeAtr: false,
      includeIchimoku: true,
      includeStochRsi: false,
      includeVwap: true,
    });

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][0]).toBe(`${API_BASE_URL}/api/news/latest`);
    expect(calls[1][0]).toContain("/api/markets/indicators?");
    expect(new URL(calls[1][0]).searchParams.get("include_atr")).toBe("false");
    expect(new URL(calls[1][0]).searchParams.get("include_ichimoku")).toBe("true");
  });

  it("gestiona el flujo de sendChatMessage con indicadores", async () => {
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce(createResponse({ indicators: { rsi: 55 } }))
      .mockResolvedValueOnce(
        createResponse({
          response: "Respuesta final",
          provider: "openai",
          used_data: true,
          sources: ["prices"],
          session_id: "chat-1",
        })
      );
    const onChunk = jest.fn();

    const result = await api.sendChatMessage(
      [{ role: "user", content: "Hola" }],
      "token",
      onChunk,
      { symbol: "BTC", interval: "4h" }
    );

    const calls = (global.fetch as jest.Mock).mock.calls;
    expect(calls[0][0]).toContain("/api/markets/indicators?");
    expect(calls[1][0]).toBe(`${API_BASE_URL}/api/ai/chat`);
    expect(onChunk).toHaveBeenCalledWith("Respuesta final");
    expect(result.messages).toHaveLength(2);
    expect(result.sources).toEqual(["prices"]);
    expect(result.sessionId).toBe("chat-1");
  });

  it("continúa aunque getIndicators falle", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    (global.fetch as jest.Mock)
      .mockRejectedValueOnce(new Error("sin datos"))
      .mockResolvedValueOnce(createResponse({ response: "Ok" }));

    const result = await api.sendChatMessage(
      [
        { role: "assistant", content: "Hola" },
        { role: "user", content: "Dame datos" },
      ],
      undefined,
      undefined,
      { symbol: "ETH", sessionId: "persisted" }
    );

    expect(warnSpy).toHaveBeenCalled();
    expect((global.fetch as jest.Mock).mock.calls[1][0]).toBe(
      `${API_BASE_URL}/api/ai/chat`
    );
    expect(result.messages[result.messages.length - 1].content).toBe("Ok");
    expect(result.sessionId).toBe("persisted");
    warnSpy.mockRestore();
  });

  it("lanza error cuando el tipo de mercado no es soportado", async () => {
    await expect(api.getMarketQuote("commodities" as any, "OIL")).rejects.toThrow(
      "Tipo de mercado no soportado: commodities"
    );
  });

  it("avisa cuando no hay cotizaciones disponibles", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce(
      createResponse({ quotes: [] }, 200)
    );

    await expect(api.getMarketQuote("crypto", "btc", "token")).rejects.toThrow(
      "No se encontró información para BTC"
    );
  });
});
