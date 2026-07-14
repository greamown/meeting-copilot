import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 240_000,
  expect: { timeout: 120_000 },
  use: {
    baseURL: process.env.BASE_URL ?? "https://localhost",
    ignoreHTTPSErrors: true,
    permissions: ["microphone"],
    launchOptions: {
      args: [
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "--use-file-for-fake-audio-capture=/app/e2e/fake-mic.wav",
      ],
    },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
  workers: 1,
});
