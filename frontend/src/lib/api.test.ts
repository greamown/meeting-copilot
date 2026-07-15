import { afterEach, expect, test, vi } from "vitest";
import { remove } from "./api";

afterEach(() => vi.unstubAllGlobals());

test("delete accepts a 204 response without parsing JSON", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 204 }));
  await expect(remove("/meetings/example")).resolves.toBeUndefined();
});
