import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
<<<<<<< Updated upstream
  fullyParallel: true,
  reporter: [["list"], ["html", { outputFolder: "playwright-report" }]],
  use: { baseURL: "http://localhost:3000", trace: "on-first-retry" },
  projects: [{ name: "Desktop Chrome", use: { ...devices["Desktop Chrome"] } }],
=======
  outputDir: "./playwright-report",
  reporter: [["html", { open: "never" }]],
  use: { baseURL: "http://localhost:3000", headless: true },
  projects: [
    { name: "Desktop Chrome", use: { ...devices["Desktop Chrome"], headless: true } },
  ],
>>>>>>> Stashed changes
});
