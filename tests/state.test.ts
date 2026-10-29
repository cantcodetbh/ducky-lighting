import { test } from "node:test";
import assert from "node:assert/strict";
import {
  layouts,
  defaultScene,
  validateScene,
  validateProfile,
  changeLayout,
  hsv,
  toHSV,
} from "../src/state";
import { keyColour } from "../src/effects";
test("ANSI61 and ISO62 geometry preserves 15 units with exact Enter and Shift", () => {
  assert.equal(layouts.ansi.keys.length, 61);
  assert.equal(layouts.iso.keys.length, 62);
  for (const layout of Object.values(layouts)) {
    assert.equal(
      new Set(layout.keys.map((k) => k.id)).size,
      layout.keys.length,
    );
    for (const k of layout.keys) {
      assert(k.x >= 0 && k.x + k.width <= 15);
      assert(k.y >= 0 && k.y <= 4);
    }
  }
  assert.equal(layouts.ansi.keys.find((k) => k.id === "2:13")?.width, 2.25);
  assert.equal(
    layouts.iso.keys.find((k) => k.id === "2:13")?.shape,
    "iso-enter",
  );
  assert.equal(layouts.iso.keys.find((k) => k.id === "3:0")?.width, 1.25);
  assert.equal(layouts.ansi.keys.find((k) => k.id === "3:0")?.width, 2.25);
  assert.deepEqual(layouts.iso.keys.find((k) => k.id === "4:5")?.leds, [
    [4, 3],
    [4, 5],
    [4, 7],
  ]);
});
test("profile validation rejects malformed/unmapped colours and roundtrips", () => {
  const scene = defaultScene();
  scene.paints["0:0"] = "#00ff00";
  assert.deepEqual(validateScene(JSON.parse(JSON.stringify(scene))), scene);
  for (const bad of [
    { ...scene, color: "#fff" },
    { ...scene, brightness: NaN },
    { ...scene, layout: "other" },
    { ...scene, paints: { "9:9": "#ffffff" } },
  ])
    assert.throws(() => validateScene(bad));
  assert.throws(() => validateProfile({ id: "x", name: "", scene }));
  const iso = {
    ...scene,
    layout: "iso" as const,
    paints: { "3:1": "#123456", "0:0": "#abcdef" },
  };
  assert.deepEqual(changeLayout(iso, "ansi").paints, { "0:0": "#abcdef" });
});
test("effect engine animates Wave/Breathing and responds to Reactive/Ripple triggers", () => {
  const s = defaultScene(),
    k = layouts.ansi.keys[0];
  for (const effect of ["Wave", "Breathing"] as const) {
    s.effect = effect;
    assert.notEqual(keyColour(s, k, 0, []), keyColour(s, k, 1000, []));
    assert.equal(keyColour(s, k, 0, [], true), keyColour(s, k, 1000, [], true));
  }
  for (const effect of ["Reactive", "Ripple"] as const) {
    s.effect = effect;
    const trigger = { x: k.x, y: k.y, id: k.id, at: 1000 };
    assert.notEqual(
      keyColour(s, k, 1000, []),
      keyColour(s, k, 1000, [trigger]),
    );
  }
  s.brightness = 0;
  assert.equal(keyColour(s, k, 0, []), "#000000");
  s.brightness = 100;
  s.paints[k.id] = "#123456";
  assert.equal(keyColour(s, k, 1000, []), "#123456");
  assert.equal(hsv(120, 1, 1), "#00ff00");
  assert.deepEqual(toHSV("#00ff00"), [120, 1, 1]);
});
