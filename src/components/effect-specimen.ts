import { layouts, defaultScene } from "../state";
import { keyColour } from "../effects";
import type { Effect } from "../types";
/** Matched-scale specimens, sampled from the same geometry and RGB engine. */
export function effectSpecimen(effect: Effect) {
  const scene = { ...defaultScene(), effect };
  const triggers = [
    { x: 5.5, y: 2, id: "2:5", at: effect === "Ripple" ? 150 : 850 },
  ];
  return `<svg viewBox="0 0 124 44" aria-hidden="true"><rect x="0" y="0" width="124" height="44" rx="3" fill="#e7e5ef"/>${layouts.ansi.keys.map((k) => `<rect x="${2 + k.x * 8}" y="${2 + k.y * 8}" width="${k.width * 8 - 1}" height="7" rx="1" fill="${keyColour(scene, k, 900, triggers)}"/>`).join("")}</svg>`;
}
