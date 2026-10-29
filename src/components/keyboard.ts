import { layouts } from "../state";
import { models } from "../data/models";
import { keyColour } from "../effects";
import type { Scene, Key, Trigger } from "../types";
const NS = "http://www.w3.org/2000/svg",
  P = 56,
  G = 5,
  BX = 29,
  BY = 30;
function svg(
  tag: string,
  attrs: Record<string, string | number> = {},
  text?: string,
): SVGElement {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  if (text !== undefined) e.textContent = text;
  return e;
}
function geometry(k: Key): Record<string, string | number> {
  const x = BX + k.x * P,
    y = BY + k.y * P,
    w = k.width * P - G,
    h = P - G;
  if (k.shape === "iso-enter")
    return {
      d: `M${x + 5} ${y - P} H${x + w - 5} Q${x + w} ${y - P} ${x + w} ${y - P + 5} V${y + h - 5} Q${x + w} ${y + h} ${x + w - 5} ${y + h} H${x + 14 + 5} Q${x + 14} ${y + h} ${x + 14} ${y + h - 5} V${y - G} H${x + 5} Q${x} ${y - G} ${x} ${y - G - 5} V${y - P + 5} Q${x} ${y - P} ${x + 5} ${y - P} Z`,
    };
  return { x, y, width: w, height: h, rx: 5 };
}
export class Keyboard {
  private previousColours = new Map<string, string>();
  private lights = new Map<string, SVGElement[]>();
  private groups = new Map<string, SVGElement>();
  constructor(
    readonly host: SVGSVGElement,
    private choose: (
      key: Key,
      event: MouseEvent | KeyboardEvent | PointerEvent,
      drag: boolean,
    ) => void,
  ) {
    host.addEventListener("pointerdown", (e) => {
      const g = (e.target as Element).closest("[data-key]");
      if (g) {
        e.preventDefault();
        (g as SVGElement).focus();
        const k = this.keys.find((k) => k.id === g.getAttribute("data-key"));
        if (k) this.choose(k, e, false);
      }
    });
    host.addEventListener("pointerover", (e) => {
      if (!(e.buttons & 1)) return;
      const g = (e.target as Element).closest("[data-key]");
      const k = this.keys.find((k) => k.id === g?.getAttribute("data-key"));
      if (k) this.choose(k, e, true);
    });
    host.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        const k = this.keys.find(
          (k) =>
            k.id ===
            (e.target as Element)
              .closest("[data-key]")
              ?.getAttribute("data-key"),
        );
        if (k) this.choose(k, e, false);
      } else if (
        ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key)
      ) {
        e.preventDefault();
        const id = (e.target as Element)
            .closest("[data-key]")
            ?.getAttribute("data-key"),
          current = this.keys.findIndex((k) => k.id === id);
        const step =
          e.key === "ArrowLeft"
            ? -1
            : e.key === "ArrowRight"
              ? 1
              : e.key === "ArrowUp"
                ? -13
                : 13;
        this.groups
          .get(
            this.keys[(current + step + this.keys.length) % this.keys.length]
              .id,
          )
          ?.focus();
      }
    });
  }
  private keys: Key[] = [];
  render(scene: Scene) {
    this.keys = layouts[scene.layout].keys;
    const m = models[scene.model];
    this.host.replaceChildren();
    this.groups.clear();
    this.lights.clear();
    this.previousColours.clear();
    this.host.setAttribute("viewBox", "0 0 898 338");
    this.host.setAttribute(
      "aria-label",
      `${m.name}, ${scene.layout.toUpperCase()}, ${this.keys.length} keys`,
    );
    const defs = svg("defs");
    const grad = svg("linearGradient", {
      id: "cap",
      x1: 0,
      y1: 0,
      x2: 0,
      y2: 1,
    });
    grad.append(
      svg("stop", {
        offset: "0%",
        "stop-color": "white",
        "stop-opacity": ".07",
      }),
      svg("stop", {
        offset: "60%",
        "stop-color": "white",
        "stop-opacity": ".01",
      }),
      svg("stop", {
        offset: "100%",
        "stop-color": "black",
        "stop-opacity": ".12",
      }),
    );
    defs.append(grad);
    this.host.append(defs);
    this.host.append(
      svg("rect", {
        x: 13,
        y: 15,
        width: 872,
        height: 310,
        rx: 10,
        fill: m.edge,
      }),
      svg("rect", {
        x: 13,
        y: 11,
        width: 872,
        height: 304,
        rx: 10,
        fill: m.case,
        stroke: "rgba(255,255,255,.12)",
        "stroke-width": 2,
      }),
      svg("rect", {
        x: 23,
        y: 23,
        width: 852,
        height: 285,
        rx: 5,
        fill: m.plate,
      }),
    );
    for (const k of this.keys) {
      const mod = k.width > 1 || k.label === "Fn";
      let fill = mod ? m.mods : m.alpha;
      if (k.id === "0:0") fill = scene.model === "llama" ? m.space : m.mods;
      if (k.id === "4:5") fill = m.space;
      const text =
        scene.model === "llama" && fill === m.space
          ? "#faffff"
          : (scene.model === "creator" && fill === m.alpha) ||
              (scene.model === "creator" && k.id === "4:5")
            ? m.legend
            : scene.model === "creator"
              ? "#f7f0ff"
              : m.legend;
      const g = svg("g", {
        "data-key": k.id,
        "data-label": k.label,
        class: "key-group",
        role: "button",
        tabindex: k.id === "0:0" ? 0 : -1,
        "aria-label": `${k.label}, row ${k.row + 1}`,
        "aria-pressed": "false",
      });
      const shape = k.shape === "iso-enter" ? "path" : "rect",
        geo = geometry(k);
      const glow = svg(shape, {
        ...geo,
        fill: "none",
        stroke: "#e79abb",
        "stroke-width": 3.8,
        "stroke-opacity": ".82",
        class: "key-light",
      });
      g.append(
        glow,
        svg(shape, {
          ...geo,
          fill,
          stroke: "#00000040",
          "stroke-width": 1.1,
          class: "key-top",
        }),
        svg(shape, { ...geo, fill: "url(#cap)", class: "cap-surface" }),
      );
      // The inset top face and narrow front wall give caps a sculpted profile
      // without changing their physical key outlines or hit geometry.
      if (shape === "rect") {
        const face = {
          x: BX + k.x * P + 3.5,
          y: BY + k.y * P + 3,
          width: k.width * P - G - 7,
          height: P - G - 9,
          rx: 3,
        };
        g.append(
          svg("rect", { ...face, fill, class: "cap-face" }),
          svg("rect", {
            ...face,
            fill: "url(#cap)",
            stroke: "rgba(255,255,255,.10)",
            "stroke-width": 0.65,
            class: "cap-face",
          }),
        );
      }
      if (scene.model === "creator") {
        const side = svg(shape, {
          ...geo,
          fill: "none",
          stroke: "#f9e7fc",
          "stroke-width": 2.5,
          "stroke-opacity": ".8",
          class: "pudding-light",
        });
        g.append(side);
        this.lights.set(k.id, [glow, side]);
      } else this.lights.set(k.id, [glow]);
      const x = BX + k.x * P,
        y = BY + k.y * P,
        w = k.width * P - G;
      let label =
        k.label === "Backspace"
          ? "Backspace"
          : k.label === "Win"
            ? "Win"
            : k.label;
      if (label === "Space")
        g.append(
          svg("path", {
            d: `M${x + w * 0.43} ${y + 25}h${w * 0.14}`,
            stroke: text,
            "stroke-opacity": ".55",
            "stroke-width": 1.3,
          }),
        );
      else {
        g.append(
          svg(
            "text",
            {
              x: x + (k.shape === "iso-enter" ? 24 : 9),
              y: y + 19,
              fill: text,
              "font-size": label.length > 4 ? 8.5 : 11,
              class: "key-label",
            },
            label,
          ),
        );
        const upper: Record<string, string> =
          scene.layout === "iso"
            ? {
                "1": "!",
                "2": '"',
                "3": "£",
                "4": "$",
                "5": "%",
                "6": "^",
                "7": "&",
                "8": "*",
                "9": "(",
                "0": ")",
                "'": "@",
                "#": "~",
                "\\": "|",
              }
            : {
                "1": "!",
                "2": "@",
                "3": "#",
                "4": "$",
                "5": "%",
                "6": "^",
                "7": "&",
                "8": "*",
                "9": "(",
                "0": ")",
                "\\": "|",
              };
        if (upper[label])
          g.append(
            svg(
              "text",
              {
                x: x + 9,
                y: y + 32,
                fill: text,
                "fill-opacity": 1,
                "font-size": 7.5,
                class: "key-label",
              },
              upper[label],
            ),
          );
      }
      g.append(
        svg(shape, {
          ...geo,
          fill: "none",
          stroke: "#9aafff",
          "stroke-width": 2.6,
          class: "selection-outline",
        }),
      );
      this.groups.set(k.id, g);
      this.host.append(g);
    }
  }
  selection(selected: Set<string>) {
    for (const [id, g] of this.groups) {
      g.classList.toggle("selected", selected.has(id));
      g.setAttribute("aria-pressed", String(selected.has(id)));
    }
  }
  animate(scene: Scene, time: number, triggers: Trigger[], reduced: boolean) {
    for (const k of this.keys) {
      const c = keyColour(scene, k, time, triggers, reduced);
      if (this.previousColours.get(k.id) === c) continue;
      this.previousColours.set(k.id, c);
      for (const e of this.lights.get(k.id) ?? []) e.setAttribute("stroke", c);
      this.groups.get(k.id)?.setAttribute("data-colour", c);
    }
  }
}
