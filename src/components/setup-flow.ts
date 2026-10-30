import { icon } from "./icons";
import {
  isHosted,
  firmwarePolicy,
  firmwarePrepare,
  firmwareInspect,
  firmwareFlash,
  firmwareDownload,
} from "../api";

type Step = 0 | 1 | 2 | 3 | 4;
interface Job {
  id: string;
  state: string;
  image: string;
  submitted: number;
  total_reports: number;
  message: string;
}
interface Policy {
  flashing_enabled: boolean;
  images_ready?: boolean;
  platform?: string;
  platform_detail?: string;
  device?: {
    connected?: boolean;
    firmware?: string;
    effects?: boolean;
    mode?: string;
  };
  loader?: { device_id: string; requires_reconnect?: boolean } | null;
  job?: Job | null;
}
const downloads =
  "https://github.com/cantcodetbh/ducky-lighting/releases/tag/v0.5.1-experimental";
const labels = ["Keyboard", "Prepare", "Connect", "Install", "Finish"];
const titles = [
  "Check your keyboard",
  "Prepare the firmware",
  "Connect in update mode",
  "Review your installation",
  "Reconnect your keyboard",
];
const leads = [
  "Start with the model label underneath your keyboard.",
  "Get the verified files ready before disconnecting anything.",
  "This starts the keyboard’s built-in updater. It does not install anything yet.",
  "Check the details below. Installation starts only when you confirm.",
  "The transfer finished. One last check on the physical keyboard.",
];

export function mountSetupFlow(companionLink: () => string) {
  const dialog = document.createElement("dialog");
  dialog.id = "setup-dialog";
  dialog.className = "setup-dialog";
  dialog.setAttribute("aria-labelledby", "setup-title");
  dialog.setAttribute("aria-describedby", "setup-lead");
  dialog.innerHTML = `
    <header class="setup-top"><span class="setup-brand">${icon("keyboard")}Keyboard setup</span><button class="icon-btn" id="setup-close" aria-label="Close setup">${icon("close")}</button></header>
    <nav class="setup-route" aria-label="Installation steps"><ol>${labels.map((label, i) => `<li data-setup-step="${i}"><span class="setup-route-mark">${i + 1}</span><span>${label}</span></li>`).join("")}</ol></nav>
    <div class="setup-body">
      <div class="setup-heading"><h2 id="setup-title" tabindex="-1"></h2><p id="setup-lead"></p></div>
      <section id="setup-hosted" hidden>
        <div class="setup-companion-mark">${icon("monitor")}</div>
        <p>The companion opens this editor on your computer and handles the USB connection. Your current lighting scene travels with you.</p>
        <a class="btn setup-primary" id="open-companion" href="ducky-lighting://open">Open companion${icon("chevron")}</a>
        <p class="setup-download">Not installed yet? <a href="${downloads}" target="_blank" rel="noopener">Download for Mac, Windows or Linux</a></p>
        <p class="setup-fine">Opening the companion does not apply colours or start a firmware update.</p>
      </section>
      <section data-setup-panel="0">
        <p id="setup-existing" class="setup-notice" hidden></p>
        <div class="setup-model"><span>Supported model</span><strong>DKME2061ST</strong><span>Ducky Mecha Mini · M032SE3AE</span></div>
        <label class="firmware-check"><input type="checkbox" id="firmware-model"> <span>The label underneath my keyboard reads <strong>DKME2061ST</strong>.</span></label>
        <p class="setup-fine">Other Ducky keyboards can look similar. The model, controller and boot configuration must match before installation is allowed.</p>
        <label class="firmware-field">What would you like to install?<select id="firmware-image"><option value="candidate">Ducky Lighting · custom9004</option><option value="restore">Original Ducky firmware · V1.10</option></select></label>
        <p id="setup-image-detail">Adds native effects and onboard static colours. Installing resets saved startup colours.</p>
        <div class="setup-caution"><strong>Experimental firmware</strong><p>Verified on one DKME2061ST using macOS. Windows and Linux physical USB flashing is unverified. A failed update can require hardware repair.</p></div>
      </section>
      <section data-setup-panel="1" hidden>
        <div class="setup-file-line">${icon("folder")}<div><strong>Official Ducky V1.10 updater</strong><span>Verified locally. The Windows EXE is never run.</span></div><span class="setup-file-state" id="setup-file-state">Not prepared</span></div>
        <button class="btn setup-primary" id="firmware-download">${icon("import")}Download & prepare</button>
        <p>Downloads the exact supported updater from Ducky’s CDN and prepares the installation and restoration files on this computer.</p>
        <details class="setup-alternative"><summary>Already have the updater?</summary><label class="firmware-field">Choose the official V1.10 updater<input type="file" accept=".exe" id="firmware-file"></label><p class="setup-fine">Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe</p></details>
        <p id="firmware-file-status" class="setup-inline-status" role="status">No keyboard command is sent during preparation.</p>
      </section>
      <section data-setup-panel="2" hidden>
        <div class="setup-gesture" aria-label="Hold the D key while reconnecting the keyboard"><span>${icon("keyboard")}</span><kbd>D</kbd><div><strong>Hold D while reconnecting</strong><span>Release it once the cable is connected.</span></div></div>
        <ol class="setup-instructions"><li>Unplug the keyboard.</li><li>Hold <kbd>D</kbd> and plug it back into a stable, direct USB port.</li><li>Release <kbd>D</kbd>. Typing and lighting may stop in update mode.</li></ol>
        <p class="setup-fine">Disconnect other Ducky or Nuvoton devices. Use your computer’s built-in or on-screen keyboard for the final typed confirmation.</p>
        <p id="setup-linux" class="setup-notice" hidden>On Linux, install the companion’s HID permissions and reconnect the keyboard before checking.</p>
        <div class="setup-connection"><span class="circle"></span><span id="setup-loader-status">Waiting for the keyboard…</span></div>
        <button class="btn setup-primary" id="firmware-inspect" disabled>Check keyboard${icon("chevron")}</button>
        <p id="firmware-probe-status" class="setup-inline-status" role="status">Checks the chip and configuration only. No erase is requested.</p>
      </section>
      <section data-setup-panel="3" hidden>
        <div id="firmware-form">
          <dl class="setup-review"><div><dt>Keyboard</dt><dd>DKME2061ST · M032SE3AE</dd></div><div><dt>Installing</dt><dd id="setup-review-image"></dd></div><div><dt>Compatibility</dt><dd>Chip and configuration checked</dd></div></dl>
          <p id="setup-check-expiry" class="setup-fine"></p>
          <div class="setup-caution"><strong>Keep the keyboard connected</strong><p>Installation erases the application and resets saved startup colours. An interrupted or incompatible update could leave the keyboard unusable. Recovery is not guaranteed.</p></div>
          <label class="firmware-check"><input type="checkbox" id="firmware-risk"><span>I accept the risk of losing keyboard functionality and needing hardware repair.</span></label>
          <label class="firmware-field" for="firmware-confirm"><span>Type <strong>FLASH DKME2061ST</strong> to confirm</span><input id="firmware-confirm" autocomplete="off" spellcheck="false" placeholder="FLASH DKME2061ST"></label>
        </div>
        <div id="firmware-progress" hidden><div class="setup-transfer">${icon("keyboard")}<strong id="setup-transfer-title">Installing firmware</strong></div><progress id="firmware-meter" max="2344" value="0" aria-label="Programming reports sent"></progress><p id="setup-progress-count"></p></div>
        <p id="firmware-job-status" class="setup-inline-status" role="status"></p>
        <details id="setup-recovery" class="setup-alternative" hidden><summary>Recovery options</summary><p>No retry, reset or restore is sent automatically. Unplug, wait for the companion to observe disconnection, then reconnect while holding D for a fresh check. If the loader is available, original V1.10 restoration is a separate confirmed operation. If it does not return, stop; hardware recovery may be needed.</p></details>
      </section>
      <section data-setup-panel="4" hidden>
        <div class="setup-finish-mark">${icon("check")}</div>
        <p class="setup-notice">All installation packets were acknowledged. This is not full flash readback or confirmation that the keyboard has booted.</p>
        <ol class="setup-instructions"><li>Unplug the keyboard.</li><li>Reconnect normally, <strong>without holding D</strong>.</li><li>Check that typing and lighting work.</li></ol>
        <div class="setup-connection"><span class="circle"></span><span id="setup-normal-status">Waiting for the normal keyboard connection…</span></div>
        <label class="firmware-check"><input type="checkbox" id="setup-boot-confirm"><span>I’ve checked: typing and lighting work.</span></label>
        <p class="setup-fine">After returning to the editor, save your preferred static startup colours again. Animation selection is not stored across unplugging yet.</p>
      </section>
      <p id="setup-status" class="setup-status" role="status" aria-live="polite"></p>
    </div>
    <footer class="setup-bottom"><button class="text-btn" id="setup-back">Back</button><span id="setup-step-count"></span><button class="btn setup-primary" id="setup-next">Continue${icon("chevron")}</button></footer>`;
  document.body.append(dialog);
  const el = <T extends HTMLElement>(id: string) =>
    dialog.querySelector<T>("#" + id)!;
  const set = (id: string, text: string) => {
    if (el(id).textContent !== text) el(id).textContent = text;
  };
  const checked = (id: string) => el<HTMLInputElement>(id).checked;
  const image = () => el<HTMLSelectElement>("firmware-image").value;
  let step: Step = 0,
    policy: Policy | null = null,
    plan: { nonce: string; device: string; expires: number } | null = null;
  let preparing = false,
    checking = false,
    submitting = false,
    awaitingOutcome = false;
  let mutationEpoch = 0,
    recoverOnOpen = true;
  let activeJob: string | null = null,
    timer: ReturnType<typeof setInterval> | undefined,
    request: Promise<void> | null = null;
  const critical = () =>
    submitting || awaitingOutcome || policy?.job?.state === "programming";
  function invalidate() {
    plan = null;
    el<HTMLInputElement>("firmware-risk").checked = false;
    el<HTMLInputElement>("firmware-confirm").value = "";
  }
  function go(next: Step) {
    step = next;
    set("setup-status", "");
    render();
    el("setup-title").focus();
    el("setup-title").scrollIntoView({ block: "nearest" });
  }
  function normal() {
    return (
      !!policy?.device?.connected &&
      !policy.loader &&
      (image() === "restore"
        ? policy.device.mode !== "available"
        : policy.device.firmware === "custom9004")
    );
  }
  function render() {
    if (
      plan &&
      (plan.expires <= Date.now() ||
        policy?.loader?.device_id !== plan.device ||
        policy.loader?.requires_reconnect)
    ) {
      invalidate();
      set(
        "firmware-probe-status",
        "The check expired or the connection changed. Check the keyboard again before continuing.",
      );
      if (step === 3 && !critical() && !activeJob) step = 2;
    }
    const busy = critical(),
      job = policy?.job,
      failed = !!activeJob && job?.id === activeJob && job.state === "failed";
    el("setup-hosted").hidden = !isHosted;
    dialog.querySelector<HTMLElement>(".setup-route")!.hidden = isHosted;
    dialog
      .querySelectorAll<HTMLElement>("[data-setup-panel]")
      .forEach(
        (panel) =>
          (panel.hidden =
            isHosted || Number(panel.dataset.setupPanel) !== step),
      );
    dialog
      .querySelectorAll<HTMLElement>("[data-setup-step]")
      .forEach((item) => {
        const n = Number(item.dataset.setupStep);
        item.dataset.state =
          n < step ? "complete" : n === step ? "current" : "next";
        if (n === step) item.setAttribute("aria-current", "step");
        else item.removeAttribute("aria-current");
      });
    set(
      "setup-title",
      isHosted
        ? "Open the desktop companion"
        : step === 3 && busy
          ? "Installing firmware"
          : step === 3 && failed
            ? "Installation stopped"
            : titles[step],
    );
    set(
      "setup-lead",
      isHosted
        ? "Your keyboard connects locally. The rest of setup happens there."
        : step === 3 && busy
          ? "Keep the cable connected and the companion open."
          : step === 3 && failed
            ? "The companion stopped at the first error. Nothing is retried automatically."
            : leads[step],
    );
    const existing = policy?.device?.effects;
    el("setup-existing").hidden = !existing;
    set(
      "setup-existing",
      "Your keyboard already has the current RGB firmware. You can close setup and keep editing, or continue to reinstall or restore it.",
    );
    set(
      "setup-image-detail",
      image() === "candidate"
        ? "Adds native effects and onboard static colours. Installing resets saved startup colours."
        : "Restores Ducky V1.10 and removes browser RGB control. This is not a backup of V1.08 or your keyboard settings.",
    );
    el<HTMLButtonElement>("setup-close").disabled = busy;
    el<HTMLButtonElement>("setup-back").disabled =
      busy || preparing || checking;
    el("setup-back").hidden = isHosted || step === 0 || step === 4;
    set(
      "setup-step-count",
      isHosted
        ? "No firmware changes from this website"
        : `Step ${step + 1} of ${labels.length}`,
    );
    el("setup-linux").hidden = policy?.platform !== "linux";
    set(
      "setup-file-state",
      preparing
        ? "Preparing…"
        : policy?.images_ready
          ? "Ready"
          : "Not prepared",
    );
    el("setup-file-state").dataset.ready = String(!!policy?.images_ready);
    el<HTMLButtonElement>("firmware-download").disabled =
      preparing || busy || !policy?.flashing_enabled;
    el<HTMLInputElement>("firmware-file").disabled =
      preparing || busy || !policy?.flashing_enabled;
    set(
      "setup-loader-status",
      policy?.loader?.requires_reconnect
        ? "Reconnect required before another check"
        : policy?.loader
          ? "Keyboard found in update mode"
          : "Waiting for update-mode connection…",
    );
    el<HTMLButtonElement>("firmware-inspect").disabled =
      !policy?.flashing_enabled ||
      !policy.images_ready ||
      !policy.loader ||
      !!policy.loader.requires_reconnect ||
      !checked("firmware-model") ||
      checking ||
      busy;
    set(
      "firmware-inspect",
      checking ? "Checking keyboard…" : plan ? "Check again" : "Check keyboard",
    );
    set(
      "setup-review-image",
      image() === "restore"
        ? "Original Ducky V1.10"
        : "Ducky Lighting · custom9004",
    );
    if (plan) {
      const seconds = Math.max(
        0,
        Math.ceil((plan.expires - Date.now()) / 1000),
      );
      set(
        "setup-check-expiry",
        `Compatibility check valid for ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}.`,
      );
    }
    el("firmware-form").hidden = busy || failed;
    el("firmware-progress").hidden = !busy && !failed;
    el("setup-recovery").hidden = !failed;
    if (job && (busy || failed)) {
      const total = job.total_reports || 2344,
        sent = Math.max(0, Math.min(job.submitted, total));
      el<HTMLProgressElement>("firmware-meter").max = total;
      el<HTMLProgressElement>("firmware-meter").value = sent;
      set(
        "setup-progress-count",
        `${sent.toLocaleString()} of ${total.toLocaleString()} reports sent`,
      );
      set("firmware-job-status", job.message);
    }
    set(
      "setup-transfer-title",
      failed
        ? "Transfer stopped"
        : awaitingOutcome && !job
          ? "Checking installation status…"
          : "Keep your keyboard connected",
    );
    set(
      "setup-normal-status",
      normal()
        ? "Keyboard detected in normal mode"
        : "Waiting for the normal keyboard connection…",
    );
    el<HTMLInputElement>("setup-boot-confirm").disabled = !normal();
    if (!normal()) el<HTMLInputElement>("setup-boot-confirm").checked = false;
    const next = el<HTMLButtonElement>("setup-next");
    set(
      "setup-next",
      isHosted
        ? "Back to editor"
        : step === 3
          ? busy
            ? "Installing…"
            : failed
              ? "Review connection"
              : "Erase & install firmware"
          : step === 4
            ? "Start editing"
            : "Continue",
    );
    next.disabled =
      !isHosted &&
      (busy ||
        preparing ||
        checking ||
        !policy ||
        !policy.flashing_enabled ||
        (step === 0 && !checked("firmware-model")) ||
        (step === 1 && !policy.images_ready) ||
        (step === 2 && !plan) ||
        (step === 3 &&
          !failed &&
          (!plan ||
            !checked("firmware-risk") ||
            el<HTMLInputElement>("firmware-confirm").value !==
              "FLASH DKME2061ST")) ||
        (step === 4 && (!normal() || !checked("setup-boot-confirm"))));
    if (!isHosted && policy && !policy.flashing_enabled)
      set(
        "setup-status",
        policy.platform_detail ??
          "Update the desktop companion to use firmware setup.",
      );
  }
  function refresh(): Promise<void> {
    if (request) return request;
    const epoch = mutationEpoch;
    request = (async () => {
      try {
        const incoming = await firmwarePolicy();
        if (epoch !== mutationEpoch) return;
        policy = incoming;
        const job = policy!.job;
        if (
          job?.state === "programming" ||
          (recoverOnOpen &&
            job?.state === "acknowledged" &&
            !!policy!.loader) ||
          (activeJob && job?.id === activeJob)
        ) {
          activeJob = job!.id;
          el<HTMLSelectElement>("firmware-image").value = job!.image;
          step = job!.state === "acknowledged" ? 4 : 3;
        }
        recoverOnOpen = false;
        awaitingOutcome = false;
        if (!job && step === 3 && submitting === false && !plan) {
          step = 2;
          set(
            "setup-status",
            "Installation was not confirmed. Check the keyboard again before continuing.",
          );
        }
        render();
      } catch {
        const uncertain = critical();
        if (!uncertain) {
          policy = null;
          invalidate();
          if (step === 3 && !activeJob) step = 2;
        }
        set(
          "setup-status",
          uncertain
            ? "The companion is not responding. Keep the keyboard connected. Do not start another installation; checking will resume when the companion responds."
            : "The local companion could not be reached. Check that it is running.",
        );
        render();
      }
    })().finally(() => {
      request = null;
    });
    return request;
  }
  el("setup-close").onclick = () => {
    if (!critical()) dialog.close();
  };
  dialog.addEventListener("cancel", (event) => {
    if (critical()) event.preventDefault();
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog && !critical()) {
      const r = dialog.getBoundingClientRect();
      if (
        event.clientX < r.left ||
        event.clientX > r.right ||
        event.clientY < r.top ||
        event.clientY > r.bottom
      )
        dialog.close();
    }
  });
  dialog.addEventListener("close", () => {
    clearInterval(timer);
    document.documentElement.classList.remove("setup-open");
  });
  el("setup-back").onclick = () => {
    if (!critical() && step > 0) {
      if (step <= 2) invalidate();
      activeJob = null;
      go((step - 1) as Step);
    }
  };
  el("firmware-model").onchange = () => {
    if (!checked("firmware-model")) invalidate();
    render();
  };
  el("firmware-image").onchange = () => {
    invalidate();
    activeJob = null;
    render();
  };
  for (const id of ["firmware-risk", "firmware-confirm", "setup-boot-confirm"])
    el(id).addEventListener("input", render);
  el("firmware-download").onclick = async () => {
    if (preparing || critical() || !policy?.flashing_enabled) return;
    preparing = true;
    invalidate();
    set(
      "firmware-file-status",
      "Downloading and verifying the exact firmware files…",
    );
    render();
    try {
      const result = await firmwareDownload();
      set("firmware-file-status", result.message);
    } catch (error) {
      set("firmware-file-status", String(error));
    } finally {
      preparing = false;
      await refresh();
    }
  };
  el<HTMLInputElement>("firmware-file").onchange = async () => {
    const file = el<HTMLInputElement>("firmware-file").files?.[0];
    if (!file || critical()) return;
    if (file.size !== 3307520) {
      set(
        "firmware-file-status",
        "Unsupported file. Choose the official DKME2061ST V1.10 updater.",
      );
      return;
    }
    preparing = true;
    invalidate();
    set(
      "firmware-file-status",
      "Verifying the updater and preparing both images locally…",
    );
    render();
    try {
      const result = await firmwarePrepare(file);
      set("firmware-file-status", result.message);
    } catch (error) {
      set("firmware-file-status", String(error));
    } finally {
      preparing = false;
      await refresh();
    }
  };
  el("firmware-inspect").onclick = async () => {
    if (
      critical() ||
      checking ||
      !policy?.loader ||
      el<HTMLButtonElement>("firmware-inspect").disabled
    )
      return;
    const device = policy.loader.device_id;
    checking = true;
    invalidate();
    set(
      "firmware-probe-status",
      "Checking chip ID and boot configuration. No erase requested…",
    );
    render();
    try {
      const result = await firmwareInspect(device);
      plan = {
        nonce: result.plan_nonce,
        device: result.device_id,
        expires: Date.now() + Math.min(result.expires_in ?? 120, 120) * 1000,
      };
      set(
        "firmware-probe-status",
        "Chip and configuration match. Continue to review your installation.",
      );
    } catch (error) {
      set("firmware-probe-status", String(error));
    } finally {
      checking = false;
      await refresh();
    }
  };
  el("setup-next").onclick = async () => {
    if (el<HTMLButtonElement>("setup-next").disabled) return;
    if (isHosted || step === 4) {
      dialog.close();
      return;
    }
    if (step === 3) {
      if (policy?.job?.id === activeJob && policy.job.state === "failed") {
        activeJob = null;
        invalidate();
        go(2);
        return;
      }
      if (!plan || critical()) return;
      const current = plan;
      mutationEpoch++;
      submitting = true;
      awaitingOutcome = true;
      render();
      try {
        const result = await firmwareFlash(
          current.nonce,
          current.device,
          image(),
          el<HTMLInputElement>("firmware-confirm").value,
          checked("firmware-risk"),
        );
        activeJob = result.job?.id ?? null;
      } catch (error) {
        set("setup-status", String(error));
      } finally {
        invalidate();
        submitting = false;
        mutationEpoch++;
        awaitingOutcome = true;
        await refresh();
      }
      return;
    }
    go((step + 1) as Step);
  };
  document.querySelector<HTMLButtonElement>("#setup-keyboard")!.onclick =
    async () => {
      document
        .querySelector<HTMLDetailsElement>("#device-section")
        ?.removeAttribute("open");
      step = 0;
      activeJob = null;
      invalidate();
      set("setup-status", "");
      el<HTMLAnchorElement>("open-companion").href = companionLink();
      render();
      dialog.showModal();
      document.documentElement.classList.add("setup-open");
      await refresh();
      if (!dialog.open) return;
      el("setup-title").focus();
      clearInterval(timer);
      timer = setInterval(() => {
        if (dialog.open) void refresh();
      }, 1200);
    };
}
