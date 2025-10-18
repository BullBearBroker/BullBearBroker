import { defineConfig, devices } from "@playwright/test";

const toStringRecord = (source: NodeJS.ProcessEnv): Record<string, string> => {
  return Object.entries(source).reduce<Record<string, string>>((acc, [key, value]) => {
    if (typeof value === "string") {
      acc[key] = value;
    } else if (value !== undefined) {
      acc[key] = String(value);
    } else {
      acc[key] = "";
    }
    return acc;
  }, {});
};

const webServerEnv = toStringRecord(process.env);
webServerEnv.NODE_ENV = webServerEnv.NODE_ENV || "test";

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
    env: webServerEnv,
  },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]], // CODEx: mezcla reporter textual y HTML silencioso
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    trace: "on-first-retry",
  }, // CODEx: unificamos opciones para CI y debug
  projects: [{ name: "Desktop Chrome", use: { ...devices["Desktop Chrome"], headless: true } }],
});
