import type { DeviceStatus, Profile } from "./types";
export const isHosted = !["127.0.0.1", "localhost", "[::1]", "::1"].includes(
  location.hostname,
);
let token = "";
async function api(path: string, body?: unknown) {
  if (isHosted) {
    if (path === "status")
      return {
        ok: true,
        mode: "demo",
        connected: false,
        name: "Ducky Mecha Mini",
        detail: "Browser editor. Open the companion to connect your keyboard.",
        capabilities: { rgb: false, effects: false },
      };
    if (path === "profiles") return { ok: true, profiles: [] };
    throw Error("Open the desktop companion to control your keyboard.");
  }
  const r = await fetch("/api/" + path, {
    headers: body
      ? { "Content-Type": "application/json", "X-Ducky-Token": token }
      : {},
    method: body ? "POST" : "GET",
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json();
  if (!r.ok || data.ok === false)
    throw Error(data.error ?? "The local service is unavailable.");
  return data;
}
export async function deviceStatus(): Promise<DeviceStatus> {
  const d = await api("status");
  token = d.token;
  return d;
}
export async function saveProfiles(profiles: Profile[]) {
  return api("profiles", { profiles });
}
export async function loadProfiles(): Promise<Profile[]> {
  return (await api("profiles")).profiles;
}
export async function applyFrame(
  layout: string,
  colours: Record<string, string>,
  deviceId: string,
) {
  return api("lighting", {
    layout,
    colours,
    device_id: deviceId,
    consent: true,
  });
}
export async function releaseDevice(deviceId: string) {
  return api("release", { device_id: deviceId, consent: true });
}

export async function firmwarePolicy() {
  if (isHosted) {
    const r = await fetch(new URL("./firmware-policy.json", document.baseURI));
    if (!r.ok) throw Error("Setup unavailable");
    return r.json();
  }
  return api("firmware");
}

export async function quitCompanion() {
  return api("companion/quit", { consent: true });
}

export async function firmwarePrepare(file: File) {
  const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = reject; reader.readAsDataURL(file); });
  return api("firmware/prepare", {updater_base64:data});
}
export async function firmwareInspect(deviceId: string) {
  return api("firmware/inspect",{device_id:deviceId,model:"DKME2061ST",consent:true});
}
export async function firmwareFlash(planNonce:string,deviceId:string,image:string,confirmation:string,acceptRisk:boolean) {
  return api("firmware/flash",{plan_nonce:planNonce,device_id:deviceId,image,model:"DKME2061ST",confirmation,accept_risk:acceptRisk,consent:true});
}

export async function firmwareDownload() { return api("firmware/prepare", {download_official:true}); }
