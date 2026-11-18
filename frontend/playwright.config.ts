import { defineConfig, devices } from "@playwright/test";

/**
 * Tests E2E + compatibilité multi-navigateurs (ISO 25010 §6.1, §6.3, §6.4).
 * Démarre automatiquement l'API (base SQLite neuve, données de démo) et le frontend compilé.
 * Mode "stack Docker" : E2E_BASE_URL=http://localhost:8080 npx playwright test
 */
const external = process.env.E2E_BASE_URL;
const baseURL = external ?? "http://localhost:4173";
const REPORTS = "../reports/e2e";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 4,
  retries: 0,
  outputDir: "test-results",
  reporter: [
    ["list"],
    ["html", { outputFolder: `${REPORTS}/html`, open: "never" }],
    ["junit", { outputFile: `${REPORTS}/junit-e2e.xml` }],
    ["json", { outputFile: `${REPORTS}/results-e2e.json` }],
  ],
  use: {
    baseURL,
    locale: "fr-FR",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "firefox", use: { ...devices["Desktop Firefox"] } },
    { name: "webkit", use: { ...devices["Desktop Safari"] } },
  ],
  webServer: external
    ? undefined
    : [
        {
          command:
            "rm -f e2e.db && BIBLIO_DATABASE_URL=sqlite:///./e2e.db BIBLIO_SEED_ON_STARTUP=true BIBLIO_BCRYPT_ROUNDS=6 " +
            "uv run uvicorn app.main:app --port 8001 --no-server-header",
          cwd: "../backend",
          url: "http://localhost:8001/api/health",
          timeout: 120_000,
          reuseExistingServer: false,
        },
        {
          command: "npx vite preview --port 4173 --strictPort",
          env: { API_URL: "http://localhost:8001" },
          url: "http://localhost:4173",
          timeout: 60_000,
          reuseExistingServer: false,
        },
      ],
});
