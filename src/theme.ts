import { icon } from "./components/icons";
export type Appearance = "light" | "dark";
const KEY = "ducky-lighting-theme-v1";
export function setupAppearance() {
  const control = document.querySelector<HTMLButtonElement>("#appearance")!;
  const glyph = document.querySelector<HTMLElement>("#appearance-icon")!;
  let preference: Appearance = "light";
  try {
    if (localStorage.getItem(KEY) === "dark") preference = "dark";
  } catch {
    /* Light is available without browser storage. */
  }
  function apply() {
    document.documentElement.dataset.theme = preference;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", preference === "dark" ? "#17151e" : "#f3f4f8");
    control.setAttribute("aria-pressed", String(preference === "dark"));
    control.title =
      preference === "dark" ? "Switch to light mode" : "Switch to dark mode";
    glyph.innerHTML = icon(preference === "dark" ? "sun" : "moon");
  }
  control.onclick = () => {
    preference = preference === "dark" ? "light" : "dark";
    try {
      localStorage.setItem(KEY, preference);
    } catch {
      /* Keep choice for this tab. */
    }
    apply();
  };
  window.addEventListener("storage", (e) => {
    if (e.key === KEY) {
      preference = e.newValue === "dark" ? "dark" : "light";
      apply();
    }
  });
  apply();
}
