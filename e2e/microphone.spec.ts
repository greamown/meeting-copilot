import { expect, test } from "@playwright/test";

test("setup microphone loads the same-origin audio worklet", async ({ page }) => {
  const browserErrors: string[] = [];
  page.on("pageerror", error => browserErrors.push(error.message));

  await page.goto("/setup");
  for (let step = 0; step < 6; step += 1) {
    await page.getByRole("button", { name: /下一步/ }).click();
  }

  await page.getByRole("button", { name: "允許並測試" }).click();
  await expect(page.getByRole("button", { name: "停止測試" })).toBeVisible({ timeout: 10_000 });
  const errors = page.locator(".alert.error");
  expect(await errors.count(), await errors.allTextContents().then(values => values.join("\n"))).toBe(0);
  await expect(page.getByText("Unable to load a worklet's module.")).toHaveCount(0);
  expect(browserErrors).toEqual([]);
});
