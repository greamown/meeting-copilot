import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { Dashboard } from "./Dashboard";

beforeEach(() => { vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ os:"Linux",python_version:"3.12",docker_available:true,ffmpeg_available:true,codex:{installed:true,authenticated:true,version:"codex 1",profile:null,model:null,provider:"codex_cli"},gpu:{available:false,gpus:[]},database:{healthy:true,latency_ms:1,dialect:"sqlite"},redis:{enabled:false,healthy:null},disk:{free_gb:10,total_gb:20} }) })); });
test("renders live system state", async () => { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><Dashboard/></MemoryRouter></QueryClientProvider>); expect(await screen.findByText("codex 1")).toBeInTheDocument(); expect(screen.getByText("開始新會議")).toBeInTheDocument(); });
