import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { Projects } from "./Projects";
import { DialogProvider } from "../components/DialogProvider";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "project-1",
          name: "Meeting Copilot",
          description: "Local-first assistant",
          goals: "Preserve decisions",
          non_goals: "Cloud audio",
          default_language: "zh-TW",
          created_at: "2026-07-14T00:00:00Z",
          updated_at: "2026-07-14T00:00:00Z",
        },
      ],
    }),
  );
});

test("lists projects and opens the create form", async () => {
  render(
    <QueryClientProvider client={new QueryClient()}>
      <DialogProvider>
        <MemoryRouter>
          <Projects />
        </MemoryRouter>
      </DialogProvider>
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Meeting Copilot")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "新增專案" }));
  expect(screen.getByRole("heading", { name: "新增專案" })).toBeInTheDocument();
  expect(screen.getByLabelText("名稱")).toBeRequired();
});
