import { test, expect } from "@playwright/test";

test("flujo completo: login → dashboard → notificaciones → logout", async ({ page }) => {
  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const fulfillJson = (data: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(data),
      });

    switch (pathname) {
      case "/api/auth/login":
        return fulfillJson({ access_token: "mock-token", refresh_token: "mock-refresh" });
      case "/api/auth/me":
        return fulfillJson({ id: "user-1", email: "test@bullbear.ai", name: "Test User" });
      case "/api/alerts":
        return fulfillJson([]);
      case "/api/news/latest":
        return fulfillJson({ articles: [] });
      case "/api/notifications/logs":
        return fulfillJson([]);
      case "/api/portfolio":
        return fulfillJson({ items: [], total_value: 0 });
      default:
        if (pathname.startsWith("/api/markets/indicators")) {
          return fulfillJson({ indicators: {} });
        }
        if (pathname.startsWith("/api/markets/history")) {
          return fulfillJson({ symbol: "BTCUSDT", interval: "1d", values: [] });
        }
        if (pathname.startsWith("/api/ai/")) {
          return fulfillJson({ messages: [] });
        }
        if (request.method() === "POST") {
          return fulfillJson({ status: "ok" });
        }
        return fulfillJson({});
    }
  });

  await page.goto("/");
  await page.getByPlaceholder("Correo electrónico").fill("test@bullbear.ai"); // CODEx: sincronizamos placeholder con i18n actual
  await page.getByPlaceholder("Contraseña").fill("123456");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page).toHaveURL(/(dashboard|\/)$/);
  await expect(page.getByText("Notificaciones en vivo")).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).first().click();
  await expect(page).toHaveURL("/");
});
