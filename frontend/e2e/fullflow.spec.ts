import { test, expect } from "@playwright/test";

test("flujo completo: login → dashboard → notificaciones → logout", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Email").fill("test@bullbear.ai");
  await page.getByPlaceholder("Contraseña").fill("123456");
  await page.getByRole("button", { name: "Iniciar sesión" }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByText("Notificaciones en vivo")).toBeVisible();
  await page.getByRole("button", { name: "Cerrar sesión" }).click();
  await expect(page).toHaveURL("/");
});
