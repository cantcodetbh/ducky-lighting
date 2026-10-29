/* Resolve the saved light/dark choice before the page paints. */
(() => {
  let theme = "light";
  try {
    if (localStorage.getItem("ducky-lighting-theme-v1") === "dark")
      theme = "dark";
  } catch {
    /* Use light. */
  }
  document.documentElement.dataset.theme = theme;
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", theme === "dark" ? "#17151e" : "#f3f4f8");
})();
