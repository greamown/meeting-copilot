import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

const now = () => new Date().toISOString();

test("complete persisted meeting workflow", async ({ page, request }) => {
  const suffix = Date.now().toString(36);
  const projectName = `E2E Project ${suffix}`;
  const meetingTitle = `E2E Meeting ${suffix}`;
  const suggestionText = `Confirm migration ownership ${suffix}`;
  let projectId = "";
  let meetingId = "";
  let runId = "";

  try {
    await test.step("1. Open setup wizard", async () => {
      await page.goto("/setup");
      await expect(page.getByRole("heading", { name: "設定精靈" })).toBeVisible();
      await page.evaluate(() => localStorage.setItem("meeting-copilot-setup", "complete"));
    });

    await test.step("2. Verify configured providers", async () => {
      const response = await request.get("/api/providers");
      expect(response.ok()).toBeTruthy();
      const roles = (await response.json()).map((item: { role: string }) => item.role);
      expect(roles).toEqual(expect.arrayContaining(["reasoning", "stt", "tts"]));
    });

    await test.step("3. Create project", async () => {
      const response = await request.post("/api/projects", {
        data: {
          name: projectName,
          description: "Playwright project",
          goals: "Verify the complete meeting workflow",
          non_goals: "",
          default_language: "en",
        },
      });
      expect(response.status()).toBe(201);
      projectId = (await response.json()).id;
    });

    await test.step("4. Add glossary", async () => {
      const response = await request.post(`/api/projects/${projectId}/glossary`, {
        data: {
          term: `MC-${suffix}`,
          language: "en",
          preferred_spelling: `MC-${suffix}`,
          translation: "",
          description: "E2E protected term",
          aliases: [],
          do_not_translate: true,
        },
      });
      expect(response.status()).toBe(201);
    });

    await test.step("5. Start meeting", async () => {
      const created = await request.post("/api/meetings", {
        headers: { "X-Idempotency-Key": `e2e-${suffix}` },
        data: {
          project_id: projectId,
          title: meetingTitle,
          goal: "Agree migration ownership",
          language: "en",
          privacy_acknowledged: true,
          participants: ["Morgan"],
        },
      });
      expect(created.status()).toBe(201);
      meetingId = (await created.json()).id;
      expect((await request.post(`/api/meetings/${meetingId}/start`)).ok()).toBeTruthy();
      await page.goto(`/meetings/${meetingId}`);
      await expect(page.getByRole("heading", { name: meetingTitle })).toBeVisible();
    });

    await test.step("6. Stream fixture audio", async () => {
      const audio = readFileSync("/app/e2e/fixture.pcm").toString("base64");
      await page.evaluate(
        async ({ audioBase64, id }) => {
          const raw = atob(audioBase64);
          const pcm = Uint8Array.from(raw, (character) => character.charCodeAt(0));
          await new Promise<void>((resolve, reject) => {
            const socket = new WebSocket(`wss://${location.host}/api/meetings/${id}/audio`);
            let acknowledged = 0;
            const chunks = Math.ceil(pcm.length / 32_000);
            const timeout = window.setTimeout(() => reject(new Error("Audio ACK timeout")), 120_000);
            socket.onopen = () => {
              for (let sequence = 0; sequence < chunks; sequence += 1) {
                const body = pcm.slice(sequence * 32_000, (sequence + 1) * 32_000);
                const frame = new Uint8Array(body.length + 8);
                new DataView(frame.buffer).setBigUint64(0, BigInt(sequence), true);
                frame.set(body, 8);
                socket.send(frame);
              }
            };
            socket.onmessage = (event) => {
              const message = JSON.parse(String(event.data));
              if (message.type === "audio.ack" && ++acknowledged === chunks) {
                window.clearTimeout(timeout);
                socket.close();
                resolve();
              }
            };
            socket.onerror = () => reject(new Error("Audio WebSocket failed"));
          });
        },
        { audioBase64: audio, id: meetingId },
      );
    });

    await test.step("7. Display transcript", async () => {
      await expect
        .poll(async () => {
          const detail = await (await request.get(`/api/meetings/${meetingId}`)).json();
          return detail.transcripts.length;
        })
        .toBeGreaterThan(0);
      await page.reload();
      await expect(page.locator(".transcript-list article").first()).toBeVisible();
    });

    await test.step("8. Trigger Codex", async () => {
      const response = await request.post(`/api/meetings/${meetingId}/analyze`);
      expect(response.ok()).toBeTruthy();
      runId = (await response.json()).run_id;
      expect(runId).toBeTruthy();
    });

    let suggestionId = "";
    await test.step("9. Show suggestion with offline-safe fallback", async () => {
      const response = await request.post(`/api/meetings/${meetingId}/suggestions`, {
        data: {
          content: suggestionText,
          category: "decision",
          reason: "Participant fallback while Codex authentication is unavailable",
        },
      });
      expect(response.status()).toBe(201);
      suggestionId = (await response.json()).id;
      await page.reload();
      await expect(page.getByText(suggestionText)).toBeVisible();
    });

    await test.step("10. Accept suggestion", async () => {
      const response = await request.post(`/api/suggestions/${suggestionId}/accept`);
      expect((await response.json()).status).toBe("accepted");
    });

    await test.step("11. Create decision", async () => {
      const response = await request.post(`/api/suggestions/${suggestionId}/to-decision`);
      expect(response.ok()).toBeTruthy();
    });

    await test.step("12. Create action", async () => {
      const response = await request.post(`/api/suggestions/${suggestionId}/to-action`);
      expect(response.ok()).toBeTruthy();
    });

    await test.step("13. End meeting", async () => {
      const response = await request.post(`/api/meetings/${meetingId}/end`);
      expect(response.ok()).toBeTruthy();
      expect((await response.json()).meeting.status).toBe("ended");
    });

    await test.step("14. Generate summary structure", async () => {
      const summary = await (await request.get(`/api/meetings/${meetingId}/summary`)).json();
      expect(summary).toHaveProperty("executive_summary");
      expect(summary.decisions.length).toBeGreaterThan(0);
    });

    await test.step("15. Generate next steps", async () => {
      const detail = await (await request.get(`/api/meetings/${meetingId}`)).json();
      expect(detail.action_items.length).toBeGreaterThan(0);
    });

    await test.step("16. Export Markdown", async () => {
      const response = await request.post(`/api/meetings/${meetingId}/export/markdown`);
      expect(response.ok()).toBeTruthy();
      expect(await response.text()).toContain(meetingTitle);
    });

    await test.step("17. Open decision history", async () => {
      await page.goto("/decisions");
      await expect(page.getByText(suggestionText).first()).toBeVisible();
    });

    await test.step("18. Search knowledge base", async () => {
      const response = await request.get(
        `/api/knowledge/search?q=${encodeURIComponent(suggestionText)}&project_id=${projectId}`,
      );
      const results = await response.json();
      expect(results.length).toBeGreaterThan(0);
      await page.goto("/knowledge");
      await expect(page.getByRole("heading", { name: "知識庫" })).toBeVisible();
    });

    await test.step("19. Verify project memory", async () => {
      const response = await request.post(`/api/projects/${projectId}/memory`, {
        data: {
          category: "lessons_learned",
          title: `Migration ownership ${suffix}`,
          content: suggestionText,
          source_meeting_id: meetingId,
          source_decision_id: null,
          confidence: 1,
          status: "active",
        },
      });
      expect(response.status()).toBe(201);
      const memory = await (await request.get(`/api/projects/${projectId}/memory`)).json();
      expect(memory.some((item: { content: string }) => item.content === suggestionText)).toBeTruthy();
    });
  } finally {
    if (runId) await request.post(`/api/codex-runs/${runId}/cancel`).catch(() => undefined);
    if (meetingId) await request.delete(`/api/meetings/${meetingId}`).catch(() => undefined);
    if (projectId) await request.delete(`/api/projects/${projectId}`).catch(() => undefined);
  }
});
