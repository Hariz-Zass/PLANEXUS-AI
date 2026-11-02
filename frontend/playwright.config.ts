import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 45000,
  retries: process.env.CI ? 1 : 0,
  use: { baseURL: "http://127.0.0.1:3000", headless: true },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    timeout: 120000,
    reuseExistingServer: !process.env.CI,
    env: { NEXT_PUBLIC_API_BASE_URL: "" }
  }
});
