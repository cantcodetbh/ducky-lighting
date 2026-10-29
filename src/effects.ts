import type { Scene, Key, Trigger } from "./types";
import { hsv, scale } from "./state";
export function keyColour(
  s: Scene,
  k: Key,
  time: number,
  triggers: Trigger[],
  reduced = false,
): string {
  const phase = ((reduced ? 0 : time) * s.speed) / 5000;
  let c = s.paints[k.id] ?? s.color;
  let fade = 1;
  if (!s.paints[k.id]) {
    if (s.effect === "Spectrum")
      c = hsv(((k.x / 15) * 300 + 335) % 360, 0.75, 1);
    if (s.effect === "Wave")
      c = hsv(((k.x / 15) * 360 - ((phase * 95) % 360) + 720) % 360, 0.75, 1);
    if (s.effect === "Breathing")
      fade = reduced ? 0.7 : 0.15 + (0.85 * (1 + Math.sin(phase * 3))) / 2;
    if (s.effect === "Reactive")
      fade = Math.max(
        0.045,
        ...triggers
          .filter((t) => t.id === k.id)
          .map((t) => Math.max(0, 1 - (time - t.at) / 1200)),
      );
    if (s.effect === "Ripple")
      fade = Math.max(
        0.045,
        ...triggers.map((t) => {
          const age = (time - t.at) / 1000;
          const d = Math.hypot(k.x - t.x, k.y - t.y);
          return age < 0 || age > 3
            ? 0
            : Math.max(0, 1 - Math.abs(d - age * (1 + s.speed * 0.35)) * 1.8) *
                (1 - age / 3);
        }),
      );
  }
  return scale(c, (s.brightness / 100) * fade);
}
