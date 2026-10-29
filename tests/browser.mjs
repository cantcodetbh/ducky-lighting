import { chromium, webkit, expect } from "@playwright/test";
import fs from "node:fs/promises";
const base = "http://127.0.0.1:8770",
  report = {
    scope:
      "Fresh isolated Chromium and WebKit browsers; real local static app and isolated device-status fixtures. Profile backup requests use an in-memory fixture. Hardware commands are intercepted; no real HID writes.",
    captures: [],
    checks: [],
    errors: [],
    expectedHttpErrors: [],
  };
const sizes = [
  { width: 1920, height: 1080 },
  { width: 1440, height: 900 },
  { width: 1280, height: 800 },
  { width: 780, height: 900 },
  { width: 390, height: 844 },
];
const variants = [
  ["black", "ansi"],
  ["black", "iso"],
  ["llama", "ansi"],
  ["creator", "ansi"],
];
await fs.mkdir("evidence/screenshots", { recursive: true });
function check(name) {
  report.checks.push(name);
  console.log("PASS", name);
}
async function contextFor(browser, viewport) {
  const c = await browser.newContext({ viewport });
  let profiles = [];
  await c.route("**/api/status", (r) =>
    r.fulfill({
      json: {
        ok: true,
        mode: "demo",
        connected: false,
        token: "test-session",
        detail: "Isolated browser fixture; no device is opened.",
        capabilities: { rgb: false, effects: false },
      },
    }),
  );
  await c.route("**/api/profiles", async (route) => {
    if (route.request().method() === "POST")
      profiles = route.request().postDataJSON().profiles;
    await route.fulfill({ json: { ok: true, profiles } });
  });
  await c.route("**/api/lighting", (r) =>
    r.fulfill({
      status: 409,
      json: {
        ok: false,
        error: "Test interception: no hardware command was sent.",
      },
    }),
  );
  const p = await c.newPage();
  p.on("pageerror", (e) => report.errors.push(e.message));
  p.on("console", (m) => {
    if (m.type() === "error") {
      if (m.text().includes("409 (Conflict)"))
        report.expectedHttpErrors.push({
          message: m.text(),
          reason:
            "Intentional rejected hardware fixture, verified error UI; no USB command sent.",
        });
      else report.errors.push(m.text());
    }
  });
  return { c, p };
}
for (const [engine, type] of [
  ["chromium", chromium],
  ["webkit", webkit],
]) {
  const browser = await type.launch();
  for (const size of sizes) {
    const { c, p } = await contextFor(browser, size);
    await p.goto(base);
    await expect(p.locator("#device-mode")).toHaveText("Demo Mode");
    for (const [model, layout] of variants) {
      await p.selectOption("#model", model);
      await p.selectOption("#layout", layout);
      await expect(p.locator("[data-key]")).toHaveCount(
        layout === "iso" ? 62 : 61,
      );
      const geometry = await p.evaluate(() => {
        const svg = document.querySelector("#keyboard"),
          stage = document
            .querySelector(".keyboard-stage")
            .getBoundingClientRect(),
          rect = svg.getBoundingClientRect(),
          shapes = [...svg.querySelectorAll(".key-top")];
        let overlaps = 0;
        for (let i = 0; i < shapes.length; i++)
          for (let j = i + 1; j < shapes.length; j++) {
            const a = shapes[i].getBBox(),
              b = shapes[j].getBBox(),
              left = Math.max(a.x, b.x) + 1,
              right = Math.min(a.x + a.width, b.x + b.width) - 1,
              top = Math.max(a.y, b.y) + 1,
              bottom = Math.min(a.y + a.height, b.y + b.height) - 1;
            if (left < right && top < bottom) {
              for (let x = left; x < right; x += 3)
                for (let y = top; y < bottom; y += 3) {
                  const pt = svg.createSVGPoint();
                  pt.x = x;
                  pt.y = y;
                  if (
                    shapes[i].isPointInFill(pt) &&
                    shapes[j].isPointInFill(pt)
                  )
                    overlaps++;
                }
            }
          }
        const clipped = shapes.some((s) => {
          const r = s.getBoundingClientRect();
          return (
            r.left < stage.left ||
            r.right > stage.right ||
            r.top < stage.top ||
            r.bottom > stage.bottom
          );
        });
        return {
          overlaps,
          clipped,
          overflow: document.documentElement.scrollWidth > innerWidth,
          ratio: rect.width / rect.height,
          visibleInInitialViewport: rect.bottom < innerHeight,
        };
      });
      expect(geometry.overlaps).toBe(0);
      expect(geometry.clipped).toBe(false);
      expect(geometry.overflow).toBe(false);
      expect(geometry.ratio).toBeCloseTo(898 / 338, 2);
      expect(geometry.visibleInInitialViewport).toBe(true);
      const file = `evidence/screenshots/${engine}-${size.width}x${size.height}-${model}-${layout}.png`;
      await p.screenshot({
        path: file,
        fullPage: true,
        animations: "disabled",
      });
      report.captures.push({
        engine,
        ...size,
        model,
        layout,
        file,
        ...geometry,
      });
    }
    await c.close();
  }
  check(
    engine +
      ": all 20 model/layout/viewport captures have correct counts, proportional SVG, no overlaps, clipping or horizontal overflow; entire keyboard visible initially",
  );
  const { c, p } = await contextFor(browser, { width: 1440, height: 900 });
  await p.goto(base);
  await expect(p.locator("#apply-hardware")).toBeDisabled();
  const hex = p.locator("#hex");
  await p.locator('[data-mode="select"]').click();
  await p.locator('[data-key="0:0"]').click();
  await p.locator('[data-key="1:1"]').click({ modifiers: ["Shift"] });
  await expect(p.locator(".key-group.selected")).toHaveCount(2);
  await hex.fill("#00FF00");
  await hex.press("Enter");
  await expect(p.locator('[data-key="0:0"]')).toHaveAttribute(
    "data-colour",
    "#00cc00",
  );
  await expect(p.locator('[data-key="1:1"]')).toHaveAttribute(
    "data-colour",
    "#00cc00",
  );
  await p.locator("#brightness").fill("100");
  await p.locator("#brightness").dispatchEvent("input");
  await expect(p.locator('[data-key="0:0"]')).toHaveAttribute(
    "data-colour",
    "#00ff00",
  );
  check(
    engine +
      ": multi-selection, HEX editing and brightness agree with the rendered frame",
  );
  await hex.fill("bad");
  await hex.press("Enter");
  await expect(p.locator("#colour-error")).not.toBeEmpty();
  await hex.fill("#123456");
  await hex.press("Enter");
  await expect(p.locator("#colour-error")).toBeEmpty();
  await p.locator('[data-mode="brush"]').click();
  const a = await p.locator('[data-key="0:1"]').boundingBox(),
    b = await p.locator('[data-key="0:4"]').boundingBox();
  await p.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await p.mouse.down();
  await p.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 15 });
  await p.mouse.up();
  await expect(p.locator('[data-key="0:3"]')).toHaveAttribute(
    "data-colour",
    "#123456",
  );
  check(engine + ": drag-to-paint works across keys");
  await p.locator("#select-all").click();
  await expect(p.locator(".key-group.selected")).toHaveCount(61);
  await p.locator("#deselect").click();
  await expect(p.locator(".key-group.selected")).toHaveCount(0);
  await p.locator("#clear").click();
  await p.locator('[data-mode="all"]').click();
  await p.locator("#picker").fill("#ff0000");
  await p.locator("#picker").dispatchEvent("input");
  await expect(p.locator('[data-key="0:0"]')).toHaveAttribute(
    "data-colour",
    "#ff0000",
  );
  await p.locator("#fine-colour summary").click();
  await p.locator("#hue").fill("120");
  await p.locator("#hue").dispatchEvent("input");
  await expect(hex).toHaveValue("#00FF00");
  const square = await p.locator("#colour-square").boundingBox();
  await p.mouse.click(
    square.x + square.width * 0.5,
    square.y + square.height * 0.4,
  );
  await expect(hex).not.toHaveValue("#00FF00");
  await p.locator("#wheel").focus();
  const old = await hex.inputValue();
  await p.keyboard.press("ArrowRight");
  await expect(hex).not.toHaveValue(old);
  check(
    engine +
      ": all-key colour, hue slider, saturation/value square and keyboard hue wheel work",
  );
  await p.locator("#reset").click();
  for (const effect of ["Wave", "Breathing"]) {
    await p.locator(`[data-effect="${effect}"]`).click();
    const before = await p
      .locator('[data-key="0:0"]')
      .getAttribute("data-colour");
    await p.waitForTimeout(400);
    expect(
      await p.locator('[data-key="0:0"]').getAttribute("data-colour"),
    ).not.toBe(before);
  }
  await p.locator("#pause").click();
  await p.waitForTimeout(80);
  const stopped = await p
    .locator('[data-key="0:0"]')
    .getAttribute("data-colour");
  await p.waitForTimeout(300);
  await expect(p.locator('[data-key="0:0"]')).toHaveAttribute(
    "data-colour",
    stopped,
  );
  await p.locator("#pause").click();
  for (const effect of ["Reactive", "Ripple"]) {
    await p.locator(`[data-effect="${effect}"]`).click();
    await p.waitForTimeout(80);
    const before = await p
      .locator('[data-key="0:0"]')
      .getAttribute("data-colour");
    await p.locator('[data-key="0:0"]').click();
    await p.waitForTimeout(60);
    expect(
      await p.locator('[data-key="0:0"]').getAttribute("data-colour"),
    ).not.toBe(before);
  }
  await p.emulateMedia({ reducedMotion: "reduce" });
  await p.locator('[data-effect="Wave"]').click();
  await p.waitForTimeout(80);
  const fixed = await p.locator('[data-key="0:0"]').getAttribute("data-colour");
  await p.waitForTimeout(300);
  await expect(p.locator('[data-key="0:0"]')).toHaveAttribute(
    "data-colour",
    fixed,
  );
  await p.emulateMedia({ reducedMotion: "no-preference" });
  check(
    engine +
      ": Wave/Breathing animate, pause freezes, Reactive/Ripple respond, reduced motion freezes autonomous movement",
  );
  await p.selectOption("#model", "creator");
  await p.selectOption("#layout", "iso");
  await p.locator('[data-key="4:5"]').click();
  await hex.fill("#669C35");
  await hex.press("Enter");
  await p.locator("#profiles-toggle").click();
  await p.locator("#profile-name").fill("Evening test");
  await p.locator("#save-form button").click();
  await expect(p.locator(".profile-load strong")).toHaveText("Evening test");
  await p.waitForTimeout(300);
  await p.reload();
  await p.locator("#profiles-toggle").click();
  await expect(p.locator("#model")).toHaveValue("creator");
  await expect(p.locator("#layout")).toHaveValue("iso");
  await expect(p.locator(".profile-load strong")).toHaveText("Evening test");
  await p.locator(".profile-actions button").first().click();
  await p.locator(".profile-rename").fill("Renamed scene");
  await p.locator(".profile-rename").press("Enter");
  await expect(p.locator(".profile-load strong")).toHaveText("Renamed scene");
  const download = p.waitForEvent("download");
  await p.locator("#export").click();
  const d = await download;
  const file = await d.path();
  const exported = JSON.parse(await fs.readFile(file, "utf8"));
  expect(exported.schema).toBe(1);
  expect(exported.profile.scene.paints["4:5"]).toBe("#669c35");
  await p.locator("#profiles-toggle").click();
  await p.locator("#import-file").setInputFiles({
    name: "roundtrip.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(exported)),
  });
  await expect(p.locator(".profile-item")).toHaveCount(2);
  await p
    .locator(".profile-actions button")
    .filter({ hasText: "Delete" })
    .last()
    .click();
  await p.getByText("Delete permanently?", { exact: true }).click();
  await expect(p.locator(".profile-item")).toHaveCount(1);
  check(
    engine +
      ": profiles create, rename, export/import, delete and persist with per-key colours/model/layout after reload",
  );
  await p.locator("#import-file").setInputFiles({
    name: "bad.json",
    mimeType: "application/json",
    buffer: Buffer.from('{"schema":42}'),
  });
  await expect(p.locator("#toast")).toContainText("version 1");
  for (const name of ["Prism", "Cobalt", "Afterglow", "Cypress"])
    await p.locator(".scene-btn").filter({ hasText: name }).click();
  await p.locator("#device-section summary").click();
  await c.route("**/api/status", (r) =>
    r.fulfill({
      json: {
        ok: true,
        mode: "detected",
        connected: true,
        token: "fixture",
        detail: "Stock firmware fixture: RGB unavailable.",
        capabilities: { rgb: false, effects: false },
      },
    }),
  );
  await p.locator("#refresh-device").click();
  await expect(p.locator("#device-mode")).toHaveText("Device detected");
  await expect(p.locator("#apply-hardware")).toBeDisabled();
  await c.route("**/api/status", (r) =>
    r.fulfill({
      json: {
        ok: true,
        mode: "available",
        connected: true,
        token: "fixture",
        device_id: "123",
        detail: "Verified custom9002 fixture.",
        capabilities: { rgb: true, effects: false },
      },
    }),
  );
  await p.locator("#refresh-device").click();
  await expect(p.locator("#apply-hardware")).toBeEnabled();
  await p.locator("#apply-hardware").click();
  await expect(p.locator("#toast")).toContainText("Test interception");
  check(
    engine +
      ": detected/available/error UI is truthful; intercepted hardware failure never reports success",
  );
  await c.close();
  await browser.close();
}
expect(report.errors).toEqual([]);
check(
  "No unexpected console errors or uncaught exceptions in either engine; two deliberate HTTP409 failures recorded separately",
);
report.completed = new Date().toISOString();
await fs.writeFile(
  "evidence/browser-results.json",
  JSON.stringify(report, null, 2) + "\n",
);
console.log("Saved browser evidence:", report.captures.length, "screenshots");
