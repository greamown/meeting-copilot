import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { CliAuth } from "./CliAuth";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      const body = url.includes("/codex/login/status")
        ? {
            started: true,
            running: true,
            completed: false,
            message: "Open the device login page\nCode: ABCD-EFGH",
          }
        : {
            installed: true,
            authenticated: false,
            version: "codex-cli 0.144.3",
            provider: "codex_cli",
            profile: null,
            model: null,
          };
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
});

test("shows the device login instructions returned by the worker", async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <CliAuth />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(/ABCD-EFGH/)).toBeInTheDocument();
  expect(screen.getByText(/尚未登入。請完成登入頁/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "測試 Codex" })).toBeDisabled();
});
