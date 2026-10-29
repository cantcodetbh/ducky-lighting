import rawLayouts from "./data/layouts.json";
import type { Key, Layout, Scene, Profile } from "./types";
export const layouts = rawLayouts as Record<
  Layout,
  { name: string; keys: Key[]; units: number }
>;
export const effects = [
  "Static",
  "Spectrum",
  "Breathing",
  "Wave",
  "Reactive",
  "Ripple",
] as const;
export const defaultScene = (): Scene => ({
  model: "black",
  layout: "ansi",
  effect: "Spectrum",
  color: "#ff6c8e",
  brightness: 80,
  speed: 5,
  paints: {},
});
export const isHex = (x: unknown): x is string =>
  typeof x === "string" && /^#[0-9a-f]{6}$/i.test(x);
export function validateScene(x: unknown): Scene {
  if (!x || typeof x !== "object")
    throw Error("Profile must contain a lighting scene.");
  const s = x as Scene;
  if (
    !["black", "llama", "creator"].includes(s.model) ||
    !["ansi", "iso"].includes(s.layout) ||
    !effects.includes(s.effect) ||
    !isHex(s.color) ||
    !Number.isFinite(s.brightness) ||
    s.brightness < 0 ||
    s.brightness > 100 ||
    !Number.isFinite(s.speed) ||
    s.speed < 1 ||
    s.speed > 10 ||
    !s.paints ||
    typeof s.paints !== "object" ||
    Array.isArray(s.paints)
  )
    throw Error("Invalid model, layout, colour or effect settings.");
  const allowed = new Set(layouts[s.layout].keys.map((k) => k.id));
  if (Object.entries(s.paints).some(([k, c]) => !allowed.has(k) || !isHex(c)))
    throw Error("Per-key colours do not match this layout.");
  return {
    model: s.model,
    layout: s.layout,
    effect: s.effect,
    color: s.color.toLowerCase(),
    brightness: s.brightness,
    speed: s.speed,
    paints: { ...s.paints },
  };
}
export function validateProfile(x: unknown): Profile {
  const p = x as Profile;
  if (
    !p ||
    typeof p.id !== "string" ||
    !/^[a-zA-Z0-9-]{1,80}$/.test(p.id) ||
    typeof p.name !== "string" ||
    !p.name.trim() ||
    p.name.length > 48
  )
    throw Error("Profile needs a name of 1–48 characters.");
  return { id: p.id, name: p.name.trim(), scene: validateScene(p.scene) };
}
export function changeLayout(scene: Scene, layout: Layout): Scene {
  const allowed = new Set(layouts[layout].keys.map((k) => k.id));
  return {
    ...scene,
    layout,
    paints: Object.fromEntries(
      Object.entries(scene.paints).filter(([k]) => allowed.has(k)),
    ),
  };
}
export function hsv(h: number, s: number, v: number): string {
  const f = (n: number) => {
    const k = (n + h / 60) % 6;
    return Math.round(255 * v * (1 - s * Math.max(0, Math.min(k, 4 - k, 1))))
      .toString(16)
      .padStart(2, "0");
  };
  return "#" + f(5) + f(3) + f(1);
}
export function toHSV(hex: string): [number, number, number] {
  const [r, g, b] = [1, 3, 5].map(
      (i) => parseInt(hex.slice(i, i + 2), 16) / 255,
    ),
    max = Math.max(r, g, b),
    min = Math.min(r, g, b),
    d = max - min;
  let h =
    d === 0
      ? 0
      : max === r
        ? ((g - b) / d) % 6
        : max === g
          ? (b - r) / d + 2
          : (r - g) / d + 4;
  return [(h * 60 + 360) % 360, max === 0 ? 0 : d / max, max];
}
export function scale(hex: string, amount: number): string {
  return (
    "#" +
    [1, 3, 5]
      .map((i) =>
        Math.round(
          parseInt(hex.slice(i, i + 2), 16) * Math.min(1, Math.max(0, amount)),
        )
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}
