const paths: Record<string, string> = {
  moon: "M20 14a8 8 0 0 1-10-10 8 8 0 1 0 10 10z",
  monitor: "M3 4h18v13H3z M8 21h8m-4-4v4",
  cursor: "m5 3 15 10-8 1-4 7z",
  chevron: "m6 9 6 6 6-6",
  keyboard:
    "M3 6h18v12H3z M6 9h1m3 0h1m3 0h1m3 0h0 M6 12h1m3 0h1m3 0h1m3 0h0 M7 15h10",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5",
  palette:
    "M12 3a9 9 0 1 0 0 18h1a2 2 0 0 0 1-4c-1-1 0-2 1-2h2a4 4 0 0 0 4-4c0-4-4-8-9-8 M7 8h.01M12 6h.01M17 9h.01M6 13h.01",
  folder: "M3 7V5h7l2 2h9v13H3z",
  settings: "M4 6h16M4 12h16M4 18h16M8 3v6m8 0v6m-6 0v6",
  export: "M12 16V3m-4 4 4-4 4 4M4 14v7h16v-7",
  reset: "M4 9a8 8 0 1 1 0 6M4 3v6h6",
  plus: "M12 5v14M5 12h14",
  play: "m8 4 12 8-12 8z",
  pause: "M8 4v16M16 4v16",
  check: "m5 12 4 4L19 6",
  brush: "m14 3 7 7-10 10H4v-7z M11 6l7 7",
  close: "m6 6 12 12M6 18 18 6",
  import: "M12 3v13m-4-4 4 4 4-4M4 17v4h16v-4",
};
export function icon(name: string): string {
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${paths[name] ?? paths.keyboard}"/></svg>`;
}
