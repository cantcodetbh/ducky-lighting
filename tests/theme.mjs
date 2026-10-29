import { chromium, webkit, expect } from "@playwright/test";
import fs from "node:fs/promises";
const report = {
  scope:
    "Fresh Chromium/WebKit contexts, real local app, intercepted profile fixtures; no physical RGB commands.",
  captures: [],
  checks: [],
  errors: [],
};
for (const [engine, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const browser = await type.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  });
  await context.route("**/api/profiles", (r) =>
    r.fulfill({ json: { ok: true, profiles: [] } }),
  );
  const page = await context.newPage();
  page.on("pageerror", (e) => report.errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") report.errors.push(m.text());
  });
  let rgbWrites = 0;
  page.on("request", (r) => {
    if (/\/api\/(lighting|release)$/.test(r.url())) rgbWrites++;
  });
  await page.goto("http://127.0.0.1:8770/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.locator("#appearance")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  const before = await page
    .locator("[data-key]")
    .evaluateAll((keys) => keys.map((k) => [k.dataset.key, k.dataset.colour]));
  await page.locator("#appearance").click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  expect(
    await page
      .locator("[data-key]")
      .evaluateAll((keys) =>
        keys.map((k) => [k.dataset.key, k.dataset.colour]),
      ),
  ).toEqual(before);
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("#appearance")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.locator("#appearance").focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.keyboard.press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const second = await context.newPage();
  await second.goto("http://127.0.0.1:8770/");
  await page.locator("#appearance").click();
  await expect(second.locator("html")).toHaveAttribute("data-theme", "light");
  await second.close();
  await page.locator("#appearance").click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  report.checks.push(
    engine +
      ": one-click light/dark, keyboard activation, persistence, cross-tab sync, no OS-following mode, unchanged RGB preview data",
  );
  const variants = [
    ["black", "ansi"],
    ["black", "iso"],
    ["llama", "ansi"],
    ["creator", "ansi"],
  ];
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1280, height: 800 },
    { width: 780, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    for (const [model, layout] of variants) {
      await page.selectOption("#model", model);
      await page.selectOption("#layout", layout);
      await expect(page.locator("[data-key]")).toHaveCount(
        layout === "iso" ? 62 : 61,
      );
      const metrics = await page.evaluate(() => {
        const r = document.querySelector("#keyboard").getBoundingClientRect();
        return {
          overflow: document.documentElement.scrollWidth > innerWidth,
          keyboardVisible: r.bottom < innerHeight,
          ratio: r.width / r.height,
          scheme: getComputedStyle(document.documentElement).colorScheme,
        };
      });
      expect(metrics.overflow).toBe(false);
      expect(metrics.keyboardVisible).toBe(true);
      expect(metrics.ratio).toBeCloseTo(898 / 338, 2);
      expect(metrics.scheme).toBe("dark");
      const file = `evidence/dark-mode/${engine}-${viewport.width}x${viewport.height}-${model}-${layout}.png`;
      await page.screenshot({ path: file, fullPage: true });
      report.captures.push({
        engine,
        ...viewport,
        model,
        layout,
        file,
        ...metrics,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.locator("#profiles-toggle").click();
  await page.screenshot({
    path: `evidence/dark-mode/${engine}-profiles.png`,
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.locator("#device-section summary").click();
  await page.screenshot({
    path: `evidence/dark-mode/${engine}-connection.png`,
    fullPage: true,
  });
  await page.keyboard.press("Escape");
  await page.locator("#fine-colour summary").click();
  await expect(page.locator("#saturation")).toBeVisible();
  await page.locator("#hex").fill("bad");
  await page.locator("#hex").press("Enter");
  await expect(page.locator("#colour-error")).not.toBeEmpty();
  await page.screenshot({
    path: `evidence/dark-mode/${engine}-error-focus.png`,
    fullPage: true,
  });
  expect(rgbWrites).toBe(0);
  report.checks.push(
    engine +
      ": 20 dark captures, native colour-scheme, unclipped keyboard, no overflow, popovers/error/focus and zero hardware writes",
  );
  await browser.close();
}
expect(report.errors).toEqual([]);
report.completed = new Date().toISOString();
await fs.writeFile(
  "evidence/dark-mode/results.json",
  JSON.stringify(report, null, 2) + "\n",
);
console.log(report.checks.join("\n"));
console.log(
  "PASS: 40 dark captures and theme behaviour in both engines; zero console errors.",
);
