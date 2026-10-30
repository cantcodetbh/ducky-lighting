import "./style.css";
import { scale } from "./state";
import { setupKeyboard, importedScene } from "./components/setup";
import { setupAppearance } from "./theme";
import { shell } from "./components/shell";
import { Keyboard } from "./components/keyboard";
import { icon } from "./components/icons";
import { effectSpecimen } from "./components/effect-specimen";
import { models } from "./data/models";
import {
  layouts,
  defaultScene,
  validateScene,
  validateProfile,
  changeLayout,
  isHex,
  hsv,
  toHSV,
  effects,
} from "./state";
import { keyColour } from "./effects";
import {
  isHosted,
  deviceStatus,
  loadProfiles,
  saveProfiles,
  applyFrame,
  saveOnboard,
  clearOnboard,
  releaseDevice,
  quitCompanion,
  applyEffect,
} from "./api";
import type {
  Scene,
  Profile,
  Mode,
  Key,
  Trigger,
  DeviceStatus,
  Model,
  Layout,
  Effect,
} from "./types";
const $ = <T extends HTMLElement = HTMLElement>(q: string) =>
  document.querySelector<T>(q)!;
$("#app").innerHTML = shell();
setupAppearance();
let scene = defaultScene(),
  profiles: Profile[] = [],
  mode: Mode = "all",
  selected = new Set<string>(),
  triggers: Trigger[] = [],
  paused = false,
  frozenTime = 0,
  phaseOffset = 0,
  status: DeviceStatus | undefined,
  busy = false,
  activeProfile = "",
  hydrated = false;
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
let onboardNote = "", savedSceneSignature = "", onboardTone = "";
let storageError = false;
try {
  const saved = localStorage.getItem("ducky-lighting-scene-v1");
  if (saved) scene = validateScene(JSON.parse(saved));
  profiles = JSON.parse(
    localStorage.getItem("ducky-lighting-profiles-v1") ?? "[]",
  ).map(validateProfile);
} catch {
  storageError = true;
}
const transferredScene = importedScene();
if (transferredScene) scene = transferredScene;
setupKeyboard(() => scene);
const keyboard = new Keyboard(
  document.querySelector<SVGSVGElement>("#keyboard")!,
  chooseKey,
);
let persistTimer: number | undefined, toastTimer: number | undefined;
function toast(text: string) {
  $("#toast").textContent = text;
  $("#toast").classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(
    () => $("#toast").classList.remove("show"),
    3600,
  );
}
function persist() {
  if(savedSceneSignature && savedSceneSignature!==JSON.stringify(scene)) {
    onboardNote="Preview changed. Save again to update your startup colours.";
    onboardTone="changed";
    hardwareUI();
  }
  clearTimeout(persistTimer);
  persistTimer = window.setTimeout(() => {
    try {
      localStorage.setItem("ducky-lighting-scene-v1", JSON.stringify(scene));
      localStorage.setItem(
        "ducky-lighting-profiles-v1",
        JSON.stringify(profiles),
      );
    } catch {
      toast("Browser storage is full. Export your profile to keep a copy.");
    }
  }, 120);
}
function now() {
  return paused ? frozenTime : performance.now() - phaseOffset;
}
function selectionUI() {
  keyboard.selection(selected);
  const n = mode === "all" ? layouts[scene.layout].keys.length : selected.size;
  $("#selected-hint").textContent =
    mode === "all"
      ? `All ${n} keys selected`
      : n === 0
        ? "Click keys to select · Shift-click to add"
        : `${n} ${n === 1 ? "key" : "keys"} selected · Shift-click to add`;
  $("#colour-scope").textContent =
    mode === "all" ? "Whole keyboard" : n ? `${n} selected` : "Choose a key";
  $("#tool-help").textContent =
    mode === "brush"
      ? "Drag across keys to paint with your current colour."
      : mode === "select"
        ? "Click to select. Shift-click to add keys, then choose a colour."
        : "Choose a colour or an effect to light the whole keyboard.";
  document.querySelectorAll<HTMLButtonElement>("[data-mode]").forEach((b) => {
    b.classList.toggle("active", b.dataset.mode === mode);
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
  });
}
function setMode(m: Mode) {
  mode = m;
  if (m === "all") selected.clear();
  selectionUI();
}
function trigger(k: Key) {
  triggers.push({ id: k.id, x: k.x, y: k.y, at: now() });
  triggers = triggers.slice(-24);
}
function chooseKey(
  k: Key,
  e: MouseEvent | KeyboardEvent | PointerEvent,
  drag: boolean,
) {
  if (drag && mode !== "brush") return;
  trigger(k);
  if (mode === "brush") {
    selected.add(k.id);
    scene.paints[k.id] = scene.color;
    persist();
    selectionUI();
    return;
  }
  mode = "select";
  if (e.shiftKey || e.metaKey || e.ctrlKey) {
    if (selected.has(k.id)) selected.delete(k.id);
    else selected.add(k.id);
  } else {
    selected = new Set([k.id]);
    const c = scene.paints[k.id];
    if (c) {
      scene.color = c;
      syncControls();
    }
  }
  selectionUI();
}
function setColour(c: string) {
  if (!isHex(c)) return;
  scene.color = c.toLowerCase();
  if (mode === "all") {
    scene.effect = "Static";
    scene.paints = {};
  } else for (const id of selected) scene.paints[id] = scene.color;
  syncControls();
  effectUI();
  persist();
}
function syncControls() {
  const [h, s, v] = toHSV(scene.color);
  $("#picker").setAttribute("value", scene.color);
  $<HTMLInputElement>("#picker").value = scene.color;
  $<HTMLInputElement>("#hex").value = scene.color.toUpperCase();
  const values: Record<string, number> = {
    hue: Math.round(h),
    saturation: Math.round(s * 100),
    value: Math.round(v * 100),
    brightness: scene.brightness,
    speed: scene.speed,
  };
  for (const [id, value] of Object.entries(values)) {
    $<HTMLInputElement>("#" + id).value = String(value);
    $("#" + id).style.setProperty(
      "--range-progress",
      (value / (id === "hue" ? 360 : id === "speed" ? 10 : 100)) * 100 + "%",
    );
    $("#" + id + "-label").textContent =
      value + ($("#" + id).dataset.unit ?? "");
  }
  $("#wheel").setAttribute("aria-valuenow", String(Math.round(h)));
  $("#wheel").setAttribute("aria-valuetext", Math.round(h) + " degrees");
  const rad = (h * Math.PI) / 180;
  $(".wheel-marker").style.left = 50 + 45 * Math.sin(rad) + "%";
  $(".wheel-marker").style.top = 50 - 45 * Math.cos(rad) + "%";
  $("#colour-square").style.background =
    `linear-gradient(to top,#000,transparent),linear-gradient(90deg,#fff,transparent),${hsv(h, 1, 1)}`;
  $(".square-marker").style.left = s * 100 + "%";
  $(".square-marker").style.top = (1 - v) * 100 + "%";
  document
    .querySelectorAll<HTMLButtonElement>(".swatch")
    .forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.colour === scene.color)),
    );
  $("#colour-error").textContent = "";
  $("#hex").removeAttribute("aria-invalid");
}
const descriptions: Record<Effect, string> = {
  Static: "A single colour, with your per-key colours preserved.",
  Spectrum: "A rainbow across the keyboard.",
  Breathing: "Your chosen colour gently fades in and out.",
  Wave: "A continuous wave of colour flows across the keys.",
  Reactive:
    "Click a preview key to make it glow. Works inside this editor; no background key capture.",
  Ripple:
    "Click a preview key to send a ripple across the board. Works inside this editor.",
};
function effectUI() {
  const still = scene.effect === "Static" || scene.effect === "Spectrum";
  $("#pause").toggleAttribute("disabled", still);
  $("#pause").title = still
    ? "Choose an animated effect to pause the preview."
    : "Freeze the current preview frame.";
  const speedAvailable = !still && scene.effect !== "Reactive";
  $("#speed").toggleAttribute("disabled", !speedAvailable);
  $("#speed-field").dataset.disabled = String(!speedAvailable);
  $("#speed").title = speedAvailable
    ? "Adjust this effect’s animation speed."
    : "Choose Breathing, Wave or Ripple to adjust speed.";

  document.querySelectorAll<HTMLButtonElement>("[data-effect]").forEach((b) => {
    b.classList.toggle("active", b.dataset.effect === scene.effect);
    b.setAttribute("aria-pressed", String(b.dataset.effect === scene.effect));
  });
  $("#effect-note").textContent =
    descriptions[scene.effect] +
    (reduced.matches ? " Reduced motion is on." : "");
  $("#pause").innerHTML =
    icon(paused ? "play" : "pause") +
    (paused ? "Resume preview" : "Pause preview");
  $("#pause").setAttribute("aria-pressed", String(paused));
  hardwareUI();
}
function rebuild() {
  keyboard.render(scene);
  keyboard.animate(scene, now(), triggers, reduced.matches);
  $<HTMLSelectElement>("#model").value = scene.model;
  $<HTMLSelectElement>("#layout").value = scene.layout;
  $("#model-caption").textContent =
    models[scene.model].description +
    " · " +
    (scene.layout === "ansi" ? "ANSI US" : "ISO UK");
  selectionUI();
  syncControls();
  effectUI();
  persist();
}
const effectSubs = [
  "Solid colour",
  "Rainbow spread",
  "Gentle fade",
  "Flowing colour",
  "Keypress glow",
  "Keypress ripple",
];
for (const [i, name] of effects.entries()) {
  const b = document.createElement("button");
  b.className = "effect-tile";
  b.dataset.effect = name;
  b.innerHTML = `<div class="effect-art">${effectSpecimen(name)}<span class="effect-check">${icon("check")}</span></div><div class="effect-name">${name}</div><div class="effect-desc">${effectSubs[i]}</div>`;
  b.onclick = () => {
    scene.effect = name;
    triggers = [];
    effectUI();
    persist();
  };
  $("#effects").append(b);
}
for (const c of [
  "#ff6c8e",
  "#ffae65",
  "#ffde6b",
  "#71dba9",
  "#55ccec",
  "#698cff",
  "#ab82f8",
]) {
  const b = document.createElement("button");
  b.className = "swatch";
  b.style.background = c;
  b.dataset.colour = c;
  b.title = c;
  b.setAttribute("aria-label", "Use " + c);
  b.onclick = () => setColour(c);
  $("#swatches").append(b);
}
const scenes = [
  { name: "Prism", effect: "Spectrum", color: "#ff6c8e", end: "#698cff" },
  { name: "Cobalt", effect: "Static", color: "#4469df", end: "#9bb9ff" },
  { name: "Afterglow", effect: "Static", color: "#f16f88", end: "#ffc5a1" },
  { name: "Cypress", effect: "Static", color: "#347758", end: "#a1d5ad" },
] as const;
for (const s of scenes) {
  const b = document.createElement("button");
  b.className = "scene-btn";
  b.innerHTML = `<span class="scene-chip" style="background:linear-gradient(120deg,${s.color},${s.end})"></span>${s.name}`;
  b.onclick = () => {
    scene.effect = s.effect;
    scene.color = s.color;
    scene.paints = {};
    if (s.effect === "Static")
      for (const k of layouts[scene.layout].keys) {
        const t = k.x / 15;
        scene.paints[k.id] =
          "#" +
          [1, 3, 5]
            .map((i) =>
              Math.round(
                parseInt(s.color.slice(i, i + 2), 16) * (1 - t) +
                  parseInt(s.end.slice(i, i + 2), 16) * t,
              )
                .toString(16)
                .padStart(2, "0"),
            )
            .join("");
      }
    syncControls();
    effectUI();
    persist();
    toast(s.name + " loaded in preview");
  };
  $("#scenes").append(b);
}
$<HTMLSelectElement>("#model").onchange = (e) => {
  scene.model = (e.target as HTMLSelectElement).value as Model;
  rebuild();
};
$<HTMLSelectElement>("#layout").onchange = (e) => {
  scene = changeLayout(scene, (e.target as HTMLSelectElement).value as Layout);
  selected.clear();
  triggers = [];
  rebuild();
};
document
  .querySelectorAll<HTMLButtonElement>("[data-mode]")
  .forEach((b) => (b.onclick = () => setMode(b.dataset.mode as Mode)));
$("#select-all").onclick = () => {
  mode = "select";
  selected = new Set(layouts[scene.layout].keys.map((k) => k.id));
  selectionUI();
};
$("#deselect").onclick = () => {
  mode = "select";
  selected.clear();
  selectionUI();
};
$("#clear").onclick = () => {
  scene.paints = {};
  persist();
  toast("Per-key colours cleared in preview");
};
$("#reset").onclick = () => {
  scene = { ...defaultScene(), model: scene.model, layout: scene.layout };
  selected.clear();
  mode = "all";
  triggers = [];
  paused = false;
  rebuild();
  toast("Lighting reset in preview");
};
$<HTMLInputElement>("#picker").oninput = (e) =>
  setColour((e.target as HTMLInputElement).value);
function commitHex() {
  const value = $<HTMLInputElement>("#hex").value.trim();
  if (isHex(value)) {
    setColour(value);
  } else {
    $("#hex").setAttribute("aria-invalid", "true");
    $("#colour-error").textContent =
      "Enter a six-digit colour, such as #FF6C8E.";
  }
}
$("#hex").addEventListener("change", commitHex);
$("#hex").addEventListener("keydown", (e) => {
  if (e.key === "Enter") commitHex();
});
for (const id of ["hue", "saturation", "value"])
  $<HTMLInputElement>("#" + id).oninput = () =>
    setColour(
      hsv(
        +$<HTMLInputElement>("#hue").value,
        +$<HTMLInputElement>("#saturation").value / 100,
        +$<HTMLInputElement>("#value").value / 100,
      ),
    );
for (const id of ["brightness", "speed"] as const)
  $<HTMLInputElement>("#" + id).oninput = (e) => {
    scene[id] = +(e.target as HTMLInputElement).value;
    $("#" + id).style.setProperty(
      "--range-progress",
      (scene[id] / (id === "speed" ? 10 : 100)) * 100 + "%",
    );
    $("#" + id + "-label").textContent =
      scene[id] + (id === "brightness" ? "%" : "");
    persist();
  };
$("#wheel").onkeydown = (e) => {
  if (["ArrowLeft", "ArrowDown", "ArrowRight", "ArrowUp"].includes(e.key)) {
    e.preventDefault();
    const [h, s, v] = toHSV(scene.color);
    setColour(
      hsv(
        (h + (["ArrowLeft", "ArrowDown"].includes(e.key) ? -2 : 2) + 360) % 360,
        s,
        v,
      ),
    );
  }
};
function squareMove(e: PointerEvent) {
  const r = $("#colour-square").getBoundingClientRect();
  setColour(
    hsv(
      +$<HTMLInputElement>("#hue").value,
      Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)),
      1 - Math.min(1, Math.max(0, (e.clientY - r.top) / r.height)),
    ),
  );
}
$("#colour-square").onpointerdown = (e) => {
  e.stopPropagation();
  $("#colour-square").setPointerCapture(e.pointerId);
  squareMove(e);
};
$("#colour-square").onpointermove = (e) => {
  if ($("#colour-square").hasPointerCapture(e.pointerId) && e.buttons)
    squareMove(e);
};
$("#pause").onclick = () => {
  if (paused) {
    phaseOffset = performance.now() - frozenTime;
    paused = false;
  } else {
    frozenTime = now();
    paused = true;
  }
  effectUI();
};
reduced.addEventListener("change", effectUI);
async function persistProfiles() {
  persist();
  try {
    await saveProfiles(profiles);
  } catch {
    toast("Saved in this browser. Local service backup is unavailable.");
  }
}
function renderProfiles() {
  const host = $("#profiles");
  host.replaceChildren();
  if (!profiles.length) {
    const p = document.createElement("p");
    p.className = "empty-profiles";
    p.textContent =
      "Your saved lighting lives here. Name your current scene to get started.";
    host.append(p);
  }
  for (const p of profiles) {
    const item = document.createElement("div");
    item.className = "profile-item";
    const load = document.createElement("button");
    load.className = "profile-load";
    const strong = document.createElement("strong");
    strong.textContent = p.name;
    const sub = document.createElement("small");
    sub.textContent = `${models[p.scene.model].name.replace("Mecha Mini · ", "")} · ${p.scene.layout.toUpperCase()} · ${p.scene.effect}`;
    load.append(strong, sub);
    load.onclick = () => {
      scene = validateScene(p.scene);
      selected.clear();
      mode = "all";
      activeProfile = p.id;
      $<HTMLInputElement>("#profile-name").value = p.name;
      rebuild();
      toast(p.name + " loaded in preview");
    };
    item.append(load);
    const actions = document.createElement("div");
    actions.className = "profile-actions";
    const rename = document.createElement("button");
    rename.textContent = "Rename";
    rename.onclick = () => {
      const input = document.createElement("input");
      input.className = "profile-rename";
      input.value = p.name;
      input.maxLength = 48;
      input.setAttribute("aria-label", "Rename " + p.name);
      load.replaceWith(input);
      input.focus();
      input.select();
      const done = () => {
        if (input.value.trim()) {
          p.name = input.value.trim();
          if (activeProfile === p.id)
            $<HTMLInputElement>("#profile-name").value = p.name;
          void persistProfiles();
          renderProfiles();
        } else {
          input.setAttribute("aria-invalid", "true");
        }
      };
      input.onkeydown = (e) => {
        if (e.key === "Enter") done();
        if (e.key === "Escape") renderProfiles();
      };
      input.onchange = done;
    };
    const del = document.createElement("button");
    del.textContent = "Delete";
    del.onclick = () => {
      if (del.dataset.confirm !== "yes") {
        del.dataset.confirm = "yes";
        del.className = "delete-confirm";
        del.textContent = "Delete permanently?";
        return;
      }
      profiles = profiles.filter((x) => x.id !== p.id);
      if (activeProfile === p.id) activeProfile = "";
      void persistProfiles();
      renderProfiles();
      toast("Profile deleted");
    };
    actions.append(rename, del);
    item.append(actions);
    host.append(item);
  }
}
$("#save-form").onsubmit = (e) => {
  e.preventDefault();
  const name = $<HTMLInputElement>("#profile-name").value.trim();
  if (!name) return;
  if (profiles.length >= 64 && !profiles.some((p) => p.id === activeProfile)) {
    toast("You can save up to 64 profiles. Export or delete one first.");
    return;
  }
  const existing = profiles.find(
    (p) => p.id === activeProfile && p.name === name,
  );
  const p = validateProfile({
    id: existing?.id ?? crypto.randomUUID(),
    name,
    scene,
  });
  if (existing) profiles = profiles.map((x) => (x.id === p.id ? p : x));
  else profiles.push(p);
  activeProfile = p.id;
  void persistProfiles();
  renderProfiles();
  toast(name + " saved");
};
$("#export").onclick = () => {
  const p = {
    schema: 1,
    profile: {
      id: activeProfile || crypto.randomUUID(),
      name: $<HTMLInputElement>("#profile-name").value.trim() || "My lighting",
      scene,
    },
  };
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(p, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "ducky-lighting-profile.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
  toast("Profile exported");
};
$("#import").onclick = () => $<HTMLInputElement>("#import-file").click();
$<HTMLInputElement>("#import-file").onchange = async (e) => {
  const input = e.target as HTMLInputElement,
    f = input.files?.[0];
  if (!f) return;
  try {
    if (f.size > 131072)
      throw Error("Choose a JSON profile smaller than 128 KB.");
    const data = JSON.parse(await f.text());
    if (data.schema !== 1)
      throw Error("Choose a Ducky Lighting version 1 JSON profile.");
    const p = validateProfile(data.profile);
    if (profiles.length >= 64)
      throw Error("Delete a profile before importing another.");
    p.id = crypto.randomUUID();
    profiles.push(p);
    scene = validateScene(p.scene);
    activeProfile = p.id;
    $<HTMLInputElement>("#profile-name").value = p.name;
    selected.clear();
    mode = "all";
    rebuild();
    renderProfiles();
    void persistProfiles();
    toast(p.name + " imported");
  } catch (error) {
    toast(
      error instanceof Error ? error.message : "Unable to import this profile.",
    );
  }
  input.value = "";
};
let clearOnboardConfirm=false;
let clearOnboardTimer:ReturnType<typeof setTimeout>|undefined;
function hardwareUI() {
  let quit = $<HTMLButtonElement>("#quit-companion");
  if (status?.can_quit && !quit) {
    quit = document.createElement("button");
    quit.id = "quit-companion";
    quit.className = "text-btn";
    quit.textContent = "Quit companion";
    quit.onclick = async () => {
      try {
        await quitCompanion();
        toast("Companion stopped. You can close this tab.");
      } catch {
        toast("The companion could not be stopped.");
      }
    };
    $(".connection-panel").append(quit);
  }
  const available = status?.mode === "available";
  const onboard=available && status?.capabilities.onboard_profiles;
  const animated = ["Wave","Breathing","Reactive","Ripple"].includes(scene.effect);
  const nativeEffects = available && status?.capabilities.effects;
  $("#save-onboard").toggleAttribute("disabled",!onboard || busy);
  $("#save-onboard").innerHTML = icon(onboardTone==="saved" ? "check" : "keyboard") + (onboardTone==="saving" ? "Saving…" : animated ? "Save static frame" : "Save to keyboard");
  $("#save-onboard").setAttribute("aria-busy",String(onboardTone==="saving"));
  $("#save-onboard").title=onboard ? "Apply and save static colours so they return after unplugging" : "Onboard saving is unavailable for this connection";
  $(".keyboard-save-state").dataset.state=onboardTone;
  $("#clear-onboard").toggleAttribute("disabled",!onboard || busy);
  $("#onboard-hint").textContent=onboard
    ? animated ? "Save keeps a still frame, not the animation." : "Save static colours to keep them after unplugging. No app needed."
    : isHosted ? "Open the companion to save colours on your keyboard."
    : available ? "Apply colours for this session. Onboard saving is unavailable with this firmware."
    : "Save colours on your keyboard to keep them after unplugging. Connect a supported keyboard to begin.";
  $("#onboard-status").textContent=onboardNote;
  $("#apply-hardware").innerHTML =
    icon("check") + (isHosted ? "Connect keyboard" : busy ? "Sending…" : animated ? "Apply effect" : "Apply to keyboard");
  $("#apply-hardware").toggleAttribute("disabled", !isHosted && (!available || busy || (animated && !nativeEffects)));
  $("#effect-note").textContent = animated
    ? nativeEffects ? "Apply runs built-in " + scene.effect.toLowerCase() + (["Reactive","Ripple"].includes(scene.effect) ? " from physical keypresses. " : " on the keyboard. ") + "Native palettes and timing may differ from this preview. Per-key painting is static-only." : "Preview only with this firmware. Install the effects firmware to run animations on your keyboard."
    : descriptions[scene.effect];
  $("#apply-hardware").title = animated && !nativeEffects ? "This firmware supports static frames only; native effects need the effects firmware" : available
    ? "Send the current preview frame to your keyboard"
    : "Connect your keyboard with verified RGB firmware to apply colours";
  $("#device-mode").textContent =
    status?.mode === "available"
      ? "Hardware control available"
      : status?.mode === "detected"
        ? "Device detected"
        : "Demo Mode";
  $(".bottom-device").dataset.mode = status?.mode ?? "demo";
  $("#device-detail").textContent =
    status?.detail ??
    "Local service unavailable. The editor still works in this browser.";
  $("#hardware-note").textContent = available
    ? nativeEffects ? "Apply runs static colours or native effects until you unplug. Save keeps a static startup frame." : "Apply tries static colours until you unplug. Save keeps them as your startup colours. Animated effects need the effects firmware."
    : status?.mode === "detected"
      ? "Keyboard detected. This firmware has no verified RGB adapter, so lighting changes affect the preview only."
      : "Preview only. Connect your Mecha Mini to check hardware control.";
  $("#preview-tag").textContent = "Local preview";
  let release = $<HTMLButtonElement>("#release");
  if (available && !release) {
    release = document.createElement("button");
    release.id = "release";
    release.className = "text-btn";
    release.textContent = "Use keyboard lighting";
    release.onclick = async () => {
      if (!status?.device_id || busy) return;
      busy = true;
      hardwareUI();
      try {
        await releaseDevice(status.device_id);
        toast("Host control released. Keyboard lighting resumed.");
      } catch (e) {
        toast((e as Error).message);
      } finally {
        busy = false;
        hardwareUI();
      }
    };
    $("#hardware-note").after(release);
  } else if (!available && release) release.remove();
}
async function refreshDevice() {
  try {
    const previousDevice=status?.device_id;
    status = await deviceStatus();
    if(previousDevice!==status.device_id){
      onboardNote="";savedSceneSignature="";onboardTone="";clearOnboardConfirm=false;clearTimeout(clearOnboardTimer);
      $("#clear-onboard").textContent="Remove saved colours";
    }
  } catch {
    status = undefined;
  }
  if (status && !hydrated) {
    hydrated = true;
    try {
      const backup = await loadProfiles();
      const known = new Set(profiles.map((p) => p.id));
      for (const p of backup) {
        try {
          const safe = validateProfile(p);
          if (!known.has(safe.id)) {
            profiles.push(safe);
            known.add(safe.id);
          }
        } catch {
          /* preserve valid local profiles */
        }
      }
      renderProfiles();
      persist();
    } catch {
      toast(
        "Profile backup could not be loaded. Your browser profiles are preserved.",
      );
    }
  }
  hardwareUI();
}
$("#save-onboard").onclick = async () => {
  if(!status?.device_id || !status.capabilities.onboard_profiles || busy)return;
  const targetDevice=status.device_id;
  const savingSignature=JSON.stringify(scene);
  busy=true;onboardTone="saving";onboardNote="Saving static colours. Keep your keyboard connected…";hardwareUI();
  const snapshot=Object.fromEntries(layouts[scene.layout].keys.map(k=>[k.id,keyColour(scene,k,now(),triggers,reduced.matches)]));
  try {
    const result=await saveOnboard(scene.layout,snapshot,targetDevice);
    if(status?.device_id!==targetDevice)throw Error("The connection changed. Reconnect and check the saved colours.");
    if(result.onboard_saved!==true)throw Error("The keyboard did not confirm an onboard save.");
    savedSceneSignature=savingSignature;
    const changed=savingSignature!==JSON.stringify(scene);
    onboardTone=changed?"changed":"saved";
    onboardNote=changed?"Previous preview saved. Save again to include your latest edits.":"Saved on the keyboard. Your static colours return after unplugging, even with the app closed.";
    toast("Colours saved to keyboard");
  } catch(error){savedSceneSignature="";onboardTone="error";onboardNote=(error as Error).message;toast(onboardNote);}
  finally{busy=false;hardwareUI();}
};
$("#clear-onboard").onclick = async () => {
  if(!status?.device_id || !status.capabilities.onboard_profiles || busy)return;
  if(!clearOnboardConfirm){
    clearOnboardConfirm=true;$("#clear-onboard").textContent="Confirm removal";
    clearOnboardTimer=setTimeout(()=>{clearOnboardConfirm=false;$("#clear-onboard").textContent="Remove saved colours";},5000);return;
  }
  clearTimeout(clearOnboardTimer);clearOnboardConfirm=false;$("#clear-onboard").textContent="Remove saved colours";
  const targetDevice=status.device_id;
  busy=true;savedSceneSignature="";onboardTone="";onboardNote="Removing saved keyboard colours…";hardwareUI();
  try{
    const result=await clearOnboard(targetDevice);
    if(status?.device_id!==targetDevice)throw Error("The connection changed. Reconnect and check the saved colours.");
    if(result.onboard_saved!==false)throw Error("The keyboard did not confirm removal.");
    onboardNote="Onboard colours removed. Built-in keyboard lighting will start on reconnect.";toast("Onboard colours removed");
  }catch(error){onboardTone="error";onboardNote=(error as Error).message;toast(onboardNote);}
  finally{busy=false;hardwareUI();}
};
$("#refresh-device").onclick = () => void refreshDevice();
$("#apply-hardware").onclick = async () => {
  if(isHosted){$("#setup-keyboard").click();return;}
  if (!status?.device_id || status.mode !== "available" || busy) return;
  busy = true;
  hardwareUI();
  const snapshot = Object.fromEntries(
    layouts[scene.layout].keys.map((k) => [
      k.id,
      keyColour(scene, k, now(), triggers, reduced.matches),
    ]),
  );
  try {
    if(["Wave","Breathing","Reactive","Ripple"].includes(scene.effect)) {
      if(!status.capabilities.effects)throw Error("This firmware cannot run native effects. No command sent.");
      const effect=scene.effect;
      await applyEffect(effect,Math.round(scene.speed),scale(scene.color,scene.brightness/100),status.device_id);
      toast(effect+" command acknowledged. The keyboard runs this effect without the browser.");
      return;
    }
    const result = await applyFrame(scene.layout, snapshot, status.device_id);
    toast(
      `Keyboard updated · ${result.accepted_count} LED commands acknowledged`,
    );
  } catch (e) {
    toast((e as Error).message);
  } finally {
    busy = false;
    hardwareUI();
  }
};
const deviceMenu = $<HTMLDetailsElement>("#device-section");
document.addEventListener("pointerdown", (e) => {
  if (!deviceMenu.contains(e.target as Node)) deviceMenu.open = false;
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") deviceMenu.open = false;
});
let lastDraw = 0;
function animate(time: number) {
  if (!document.hidden && time - lastDraw >= 16) {
    keyboard.animate(scene, now(), triggers, reduced.matches);
    triggers = triggers.filter((t) => now() - t.at < 3500);
    lastDraw = time;
  }
  requestAnimationFrame(animate);
}
rebuild();
renderProfiles();
requestAnimationFrame(animate);
void refreshDevice();
setInterval(() => void refreshDevice(), 5000);
if (storageError)
  toast(
    "Some saved browser data was invalid. Valid profiles in the local service will be restored.",
  );

if (transferredScene)
  toast("Scene opened from the website. Apply when you are ready.");
