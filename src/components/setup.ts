import { mountSetupFlow } from "./setup-flow";
import { validateScene } from "../state";
import type { Scene } from "../types";
export function encodeScene(scene: Scene) {
  return btoa(
    String.fromCharCode(
      ...new TextEncoder().encode(JSON.stringify(validateScene(scene))),
    ),
  )
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}
export function importedScene(): Scene | null {
  const hash = new URLSearchParams(location.hash.slice(1));
  const encoded = hash.get("scene");
  if (!encoded) return null;
  try {
    if (encoded.length > 16000) throw Error();
    const raw = atob(encoded.replace(/-/g, "+").replace(/_/g, "/"));
    const scene = validateScene(
      JSON.parse(
        new TextDecoder().decode(Uint8Array.from(raw, (c) => c.charCodeAt(0))),
      ),
    );
    history.replaceState(null, "", location.pathname + location.search);
    return scene;
  } catch {
    return null;
  }
}
export function setupKeyboard(getScene: () => Scene) {
  mountSetupFlow(
    () =>
      "ducky-lighting://open?scene=" +
      encodeURIComponent(encodeScene(getScene())),
  );
}
