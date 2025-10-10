import { test, expect } from "@playwright/test";

const jsonResponse = (payload: unknown) => ({
  status: 200,
  contentType: "application/json",
  body: JSON.stringify(payload),
});

test.describe("Flujo de autenticación", () => {
  test("login → dashboard → logout", async ({ page }) => {
    const profile = { id: "1", email: "user@example.com", name: "Ana" };

    await page.route("**/api/auth/login", (route) =>
      route.fulfill(jsonResponse({ access_token: "token", refresh_token: "refresh" })),
    );
    await page.route("**/api/auth/me", (route) => route.fulfill(jsonResponse(profile)));
    await page.route("**/api/portfolio", (route) =>
      route.fulfill(jsonResponse({ items: [], total_value: 0 })),
    );
    await page.route("**/api/alerts", (route) => route.fulfill(jsonResponse([])));
    await page.route("**/api/news/latest", (route) =>
      route.fulfill(jsonResponse({ articles: [] })),
    );
    await page.route("**/api/markets/crypto/prices**", (route) =>
      route.fulfill(
        jsonResponse({
          quotes: [
            { symbol: "BTCUSDT", price: 50000, raw_change: 2.1, source: "Test", type: "crypto" },
          ],
        }),
      ),
    );
    await page.route("**/api/markets/stocks/quotes**", (route) =>
      route.fulfill(
        jsonResponse({
          quotes: [
            { symbol: "AAPL", price: 180.5, raw_change: 1.1, source: "Test", type: "stock" },
          ],
        }),
      ),
    );
    await page.route("**/api/markets/forex/rates**", (route) =>
      route.fulfill(
        jsonResponse({
          quotes: [
            { symbol: "EUR/USD", price: 1.08, raw_change: -0.3, source: "Test", type: "forex" },
          ],
        }),
      ),
    );
    await page.route("**/api/markets/indicators**", (route) =>
      route.fulfill(
        jsonResponse({
          symbol: "BTCUSDT",
          type: "crypto",
          interval: "1h",
          count: 1,
          indicators: { close: 12345 },
          series: { closes: [1, 2, 3] },
        }),
      ),
    );
    await page.route("**/api/markets/history/**", (route) =>
      route.fulfill(
        jsonResponse({
          symbol: "BTCUSDT",
          interval: "1h",
          source: "MockSource",
          values: [
            {
              timestamp: "2024-01-01T00:00:00Z",
              open: 1,
              high: 1.2,
              low: 0.9,
              close: 1.1,
              volume: 100,
            },
          ],
        }),
      ),
    );
    await page.route("**/api/ai/chat", (route) =>
      route.fulfill(
        jsonResponse({
          response: "Insight generado",
          used_data: true,
          sources: ["mock"],
        }),
      ),
    );

    page.on("websocket", (ws) => {
      if ("close" in ws && typeof (ws as { close?: () => void }).close === "function") {
        (ws as { close: () => void }).close();
      }
    });

    await page.goto("/login");

    await page.getByPlaceholder(/correo electrónico/i).fill("user@example.com");
    await page.getByPlaceholder(/contraseña/i).fill("supersecret");
    await page.getByRole("button", { name: /iniciar sesión/i }).click();

    await expect(page).toHaveURL(/\/?$/);
    await expect(page.getByTestId("dashboard-shell")).toBeVisible();
    await expect(page.getByRole("heading", { name: /Ana/ })).toBeVisible();

    await page
      .getByTestId("dashboard-content")
      .getByRole("button", { name: /Cerrar sesión/i })
      .first()
      .click();

    await expect(page).toHaveURL(/login/);
    await expect(page.getByRole("heading", { name: /Iniciar sesión/i })).toBeVisible();
  });
});
