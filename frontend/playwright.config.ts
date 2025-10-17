import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true, // CODEx: mantener ejecución paralela para suites largas
  outputDir: "./playwright-report", // CODEx: centraliza reportes fuera de .next
  // QA 2.7-I: webServer robusto para Next.js en frontend
  webServer: {
    command: "node ./node_modules/.bin/next dev",
    cwd: "frontend",
    port: 3000,
    reuseExistingServer: true,
    timeout: 180000,
    env: { ...process.env },
  },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]], // CODEx: mezcla reporter textual y HTML silencioso
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    trace: "on-first-retry",
  }, // CODEx: unificamos opciones para CI y debug
  projects: [{ name: "Desktop Chrome", use: { ...devices["Desktop Chrome"], headless: true } }],
});
