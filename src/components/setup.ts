import { icon } from "./icons";
import { isHosted, firmwarePolicy, firmwarePrepare, firmwareInspect, firmwareFlash, firmwareDownload } from "../api";
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
  const dialog = document.createElement("dialog");
  dialog.className = "setup-dialog"; dialog.id = "setup-dialog";
  dialog.setAttribute("aria-labelledby", "setup-title");
  dialog.innerHTML = `<div class="section-head"><div><h2 id="setup-title">Set up your keyboard</h2><p>Install the companion, connect, and start editing.</p></div><button class="icon-btn" id="setup-close" aria-label="Close setup">${icon("close")}</button></div>
  <ol class="setup-steps">
    <li><span class="setup-step-label">Companion</span><div><strong id="setup-companion-title"></strong><p id="setup-companion-detail"></p><a class="btn small" id="open-companion" href="ducky-lighting://open">Open companion</a><p><a href="https://github.com/cantcodetbh/ducky-lighting/releases/tag/v0.3.0-experimental" target="_blank" rel="noopener">Download for Mac, Windows or Linux</a></p><p class="setup-download-note">Experimental release. Windows/Linux RGB is not physically validated. Mac and Windows installers are not publisher signed.</p></div></li>
    <li><span class="setup-step-label">Keyboard</span><div><strong id="setup-device-title">Connect your Mecha Mini</strong><p id="setup-device-detail"></p></div></li>
    <li><span class="setup-step-label">Firmware</span><div><strong id="setup-firmware-title"></strong><p id="setup-firmware-detail"></p>
      <details id="firmware-tools"><summary>Install or restore firmware</summary>
        <div id="firmware-form">
          <p class="firmware-warning">Experimental: tested on one DKME2061ST. An interrupted or incompatible update could leave the keyboard unusable and require hardware repair. Recovery after a failed application is not proven. There is no full flash readback.</p>
          <label class="firmware-check"><input type="checkbox" id="firmware-model"> I checked the label underneath: DKME2061ST.</label>
          <button class="btn small" id="firmware-download">Prepare official firmware</button><p>Downloads the pinned V1.10 updater directly from Ducky’s CDN to this computer. Verifies and extracts it without running the EXE. No erase is requested.</p><label class="firmware-field">Or choose a local V1.10 updater <input type="file" accept=".exe" id="firmware-file"></label><p id="firmware-file-status">Optional: choose Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe. It stays local and is never executed.</p>
          <p>Use a stable direct USB connection. Disconnect other Ducky/Nuvoton devices. Keep this companion open. Unplug the keyboard, hold <kbd>D</kbd> while reconnecting, then release it. Typing and lighting may stop in bootloader mode.</p>
          <button class="btn small" id="firmware-inspect" disabled>Check bootloader</button><p id="firmware-probe-status">This check sends only CONNECT, chip-ID and configuration queries. It does not erase flash.</p>
          <label class="firmware-field">Image <select id="firmware-image"><option value="candidate">Install custom9002 · browser RGB</option><option value="restore">Restore manufacturer V1.10 · built-in lighting</option></select></label>
          <p>Restoration is V1.10, not a backup of V1.08 or your saved keyboard settings. If a failed update still permits D-on-connect, reconnect and run a fresh check before a separate restoration attempt. If the loader does not return, stop; hardware recovery may be needed.</p>
          <label class="firmware-check"><input type="checkbox" id="firmware-risk"> I accept the risk of losing keyboard functionality and needing hardware repair.</label>
          <label class="firmware-field">Type FLASH DKME2061ST to confirm <input id="firmware-confirm" autocomplete="off" spellcheck="false" placeholder="FLASH DKME2061ST"></label>
          <button class="btn" id="firmware-install" disabled>Erase application and install firmware</button>
        </div>
      </details>
      <div id="firmware-progress" hidden><progress id="firmware-meter" max="1164" value="0" aria-label="Programming reports submitted"></progress><p id="firmware-job-status" role="status"></p></div>
    </div></li>
  </ol><p class="setup-status" id="setup-status" role="status"></p>`;
  document.body.append(dialog);
  const el = <T extends HTMLElement>(id:string) => dialog.querySelector<T>("#"+id)!;
  const set = (id:string,text:string) => { el(id).textContent=text; };
  let policy:any=null, plan:{nonce:string;device:string}|null=null, preparing=false, checking=false;
  const update = () => {
    const running=policy?.job?.state === "programming";
    el<HTMLButtonElement>("firmware-inspect").disabled = !policy?.flashing_enabled || !policy?.images_ready || !policy?.loader || !el<HTMLInputElement>("firmware-model").checked || preparing || checking || running;
    el<HTMLButtonElement>("firmware-install").disabled = !plan || !policy?.flashing_enabled || running || !el<HTMLInputElement>("firmware-model").checked || !el<HTMLInputElement>("firmware-risk").checked || el<HTMLInputElement>("firmware-confirm").value !== "FLASH DKME2061ST";
    el<HTMLInputElement>("firmware-file").disabled = running || preparing;
    el<HTMLButtonElement>("firmware-download").disabled = running || preparing;
    if(policy?.loader && plan && plan.device !== policy.loader.device_id) plan=null;
    if(!policy?.loader && !running) plan=null;
  };
  const refresh = async () => {
    try {
      policy=await firmwarePolicy();
      const supported=policy.state === "already_supported";
      set("setup-device-title",policy.device?.connected ? "Keyboard detected" : policy.loader ? "Bootloader detected" : "Connect your Mecha Mini normally");
      set("setup-device-detail",supported ? "Custom9002 detected. Close setup and use Apply to keyboard." : "Only the researched DKME2061ST / M032SE3AE is supported. A product name or USB ID alone is not enough.");
      set("setup-firmware-title",supported ? "RGB firmware is already installed" : isHosted ? "Firmware setup runs in the companion" : policy.flashing_enabled ? "Experimental firmware installation" : "Firmware installation requires macOS");
      set("setup-firmware-detail",supported ? "No update is needed. Advanced tools below can restore manufacturer V1.10." : isHosted ? "Open the local companion to verify your updater, inspect the bootloader and install firmware. The hosted page never sends hardware commands." : policy.flashing_enabled ? "The exact tested custom9002 image can be prepared from your official updater. Every installation checks chip identity and configuration before erasing." : policy.platform_detail ?? "Install the latest macOS companion to use the firmware tools.");
      el("firmware-tools").hidden=!policy.flashing_enabled || isHosted;
      const job=policy.job;el("firmware-progress").hidden=!job;
      if(job){el<HTMLProgressElement>("firmware-meter").max=job.total_reports;el<HTMLProgressElement>("firmware-meter").value=job.submitted;set("firmware-job-status",job.message);}
      update();
    } catch(error){set("setup-status",String(error));}
  };
  el<HTMLButtonElement>("setup-close").onclick=()=>dialog.close();
  dialog.addEventListener("click", e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
  for(const id of ["firmware-model","firmware-risk","firmware-confirm"]) el(id).addEventListener("input",update);
  el<HTMLButtonElement>("firmware-download").onclick=async()=>{
    preparing=true;plan=null;update();set("firmware-file-status","Downloading the exact official updater and checking both image hashes…");
    try{const result=await firmwareDownload();set("firmware-file-status",result.message);}catch(error){set("firmware-file-status",String(error));}finally{preparing=false;await refresh();}
  };
  el<HTMLInputElement>("firmware-file").onchange=async()=>{
    const file=el<HTMLInputElement>("firmware-file").files?.[0];if(!file)return;
    if(file.size!==3307520){set("firmware-file-status","Unsupported file size. Choose the official DKME2061ST V1.10 updater.");return;}
    preparing=true;plan=null;update();set("firmware-file-status","Verifying and preparing the two exact images locally…");
    try{const result=await firmwarePrepare(file);set("firmware-file-status",result.message);}catch(error){set("firmware-file-status",String(error));}finally{preparing=false;await refresh();}
  };
  el<HTMLButtonElement>("firmware-inspect").onclick=async()=>{
    checking=true;plan=null;update();set("firmware-probe-status","Checking chip ID and boot configuration. No erase requested…");
    try{const result=await firmwareInspect(policy.loader.device_id);plan={nonce:result.plan_nonce,device:result.device_id};set("firmware-probe-status",result.message+" Confirmation expires after two minutes.");}catch(error){set("firmware-probe-status",String(error));}finally{checking=false;await refresh();}
  };
  el<HTMLButtonElement>("firmware-install").onclick=async()=>{
    if(!plan)return;
    const current=plan;plan=null;update();
    try{await firmwareFlash(current.nonce,current.device,el<HTMLSelectElement>("firmware-image").value,el<HTMLInputElement>("firmware-confirm").value,el<HTMLInputElement>("firmware-risk").checked);el<HTMLInputElement>("firmware-confirm").value="";el<HTMLInputElement>("firmware-risk").checked=false;}catch(error){set("setup-status",String(error));}
    await refresh();
  };
  let timer:ReturnType<typeof setInterval>|undefined;
  dialog.addEventListener("close",()=>{clearInterval(timer);});
  document.querySelector<HTMLButtonElement>("#setup-keyboard")!.onclick=async()=>{
    document.querySelector<HTMLDetailsElement>("#device-section")?.removeAttribute("open");
    dialog.showModal();
    const link=el<HTMLAnchorElement>("open-companion");link.href="ducky-lighting://open?scene="+encodeURIComponent(encodeScene(getScene()));link.hidden=!isHosted;
    set("setup-companion-title",isHosted ? "Open the desktop companion" : "Local companion is running");
    set("setup-companion-detail",isHosted ? "Open this scene in your local editor. Opening the companion does not apply colours or start flashing." : "Profiles and USB operations stay on this computer.");
    set("setup-status", "No firmware operation starts until you explicitly confirm an installation.");
    await refresh();clearInterval(timer);timer=setInterval(()=>{if(dialog.open)void refresh();},1500);
  };
}
