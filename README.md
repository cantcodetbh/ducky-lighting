# Ducky Lighting

Browser RGB editor and local USB companion for the Ducky Mecha Mini. Light/dark themes, accurate ANSI/ISO layouts, per-key colours, animated previews and saved profiles. No account or cloud USB access.

**Experimental release.** Physically researched on one **DKME2061ST / M032SE3AE**. Related Ducky models are not assumed compatible. Windows/Linux RGB communication has not been physically validated. Mac and Windows installers are not publisher signed. Firmware installation can render a keyboard unusable; interrupted-flash recovery is unproven.

[Open the editor](https://cantcodetbh.github.io/ducky-lighting/) · [Download installers](https://github.com/cantcodetbh/ducky-lighting/releases/tag/v0.4.0-experimental)

## Use it

1. Download the installer for your computer. Mac: open the DMG and drag Ducky Lighting into Applications. Windows: run the per-user setup. Debian/Ubuntu: install the DEB using your package manager. Linux portable: extract and run `DuckyLighting/DuckyLighting`; this archive does not register URL handlers or install device permissions.
2. Open Ducky Lighting. It starts its own service on `127.0.0.1:8770` and opens the local editor in your browser. No Python/Node setup is needed for installers. Safari and Chromium work.
3. The hosted editor's **Connect keyboard** button opens setup and the installed companion, carrying your scene as a preview. Browser external-app confirmation may appear. Apply to hardware is always explicit in the local editor.
4. If the compatible custom9002 firmware is already installed, use **Apply to keyboard**. This sends one current frame; preview animations do not stream continuously. Stock firmware does not have a verified host RGB protocol here.

The Windows/Linux installers and their startup/install/uninstall paths are tested in GitHub-hosted VMs. Firmware packet code is also tested against Nuvoton's actual C parser with RAM-only flash/peripheral stubs and synthetic images, including 90 failure cases. These tests do **not** emulate real USB delivery or validate physical Windows/Linux keyboard communication. Do not treat a green VM build as hardware compatibility proof.

## Experimental firmware installation — macOS, Windows and Linux companions

Open **device menu → Set up keyboard → Install or restore firmware**. The website itself does not get USB access; firmware operations run in the local companion.

- Confirm the underside label is exactly **DKME2061ST**. Do not try another keyboard because its name looks similar. Use a stable direct cable, disconnect other Nuvoton/Ducky devices and have another way to type if necessary.
- Click **Prepare official firmware** to retrieve the pinned file directly from Ducky’s CDN, or supply your own official `Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe`. The app never runs this EXE and never uploads it to the hosted site. Its complete SHA-256 must be `6d5b1a8fb16c53fc2875dad5399cd574b1fc05eef83141dd89fbcee0ede5aab8`. Other versions are rejected, not guessed. This repository does not redistribute the official updater or complete manufacturer firmware.
- It extracts exactly EXE offsets `0x20F0B8..0x21EA20` (63,848 bytes), verifies the following length word and stock SHA-256, then applies the fixed custom9002 patch. Candidate SHA-256 must be `d85ee17eeaf68e14d8634ab5d0a59f2ae551ea9aa3c6ded9451ba3fed13458fc`; manufacturer V1.10 restoration SHA-256 is `fb29585b17a0ee1883287def35a1b107695a13c4dc85355cb27f54921ea5f514`.
- Unplug, hold **D**, reconnect, release D. Click **Check bootloader**. This explicitly sends CONNECT / GET_DEVICE_ID / READ_CONFIG, not erase. The interface descriptor (or strictly equivalent Windows representation), one connected loader, current connection identity, PDID `0x01132E10` and exact measured CONFIG words must match. A mismatch stops the flow.
- Choose custom9002 or manufacturer V1.10. Read the risk, tick acceptance and type **FLASH DKME2061ST**. Only then click **Erase application and install firmware**. Confirmation expires in two minutes and is bound to that connection.
- Keep the cable and companion connected while it runs. Every fixed report must pass checksum/sequence checks; the first failure stops without retry, resume, reset or fallback programming. The Mac helper independently rechecks the complete image hash before opening USB and the device identity before each report. Windows/Linux retain one open handle from inspection through confirmation and independently verify the image before programming. A disconnection never causes the helper to reopen a path or retry. The fixed operation targets APROM offset zero; there is no configuration-write, loader-update, unlock or generic packet API.
- After all packets are acknowledged, reconnect normally with D released and check typing and lighting. Acknowledgement is **not** full flash readback or proof the keyboard booted. If it fails and D-on-connect still works, a **fresh** connection/check can permit a separate manufacturer V1.10 restoration attempt. If the loader does not return, stop; hardware repair may be needed. Restoration is not an installed V1.08 backup and saved keyboard settings may be lost.

Only normal updates on one keyboard have been physically demonstrated. There is no guaranteed recovery after power loss or invalid application flash. Windows/Linux firmware installation is now enabled and experimental. The portable HID transport, framing, failure handling and same-handle check/confirm workflow pass software and VM tests; physical USB flashing on those operating systems remains unverified. Never disable OS protections globally to run a download.

## Build and test

Node.js 22, Python 3.11; macOS needs Xcode command-line tools, Windows needs NSIS, Linux needs dpkg-deb/libudev and a desktop environment. Linux packages target x64/glibc 2.35+; there are no ARM Windows/Linux builds.

```sh
npm ci
python3 -m venv .venv-release
.venv-release/bin/python -m pip install -r packaging/requirements.txt
npm test
python3 scripts/test_firmware.py
.venv-release/bin/python scripts/build_installers.py
```

On Windows use `.venv-release\Scripts\python`. The manual build workflow tests all four native runners and creates installers. Firmware tests use only RAM; no test invokes a real programming command. `scripts/verify_installers.py` is restricted to disposable CI runners. Source launch: `npm run build`, `python3 scripts/build_native.py` on Mac, then `python3 companion.py`; `npm run dev` is frontend development with API proxy.

On Windows, the companion uses the built-in HID driver; no Zadig or replacement driver is needed. The helper runs without a console window. On Linux, the DEB installs active-user hidraw permissions for normal3233:6301 and loader0416:3F00. The loader ID is shared with other Nuvoton boards, so the application also verifies descriptor, chip and configuration. Reconnect after installing the permissions. The portable archive includes `70-ducky-lighting.rules`; install it into `/etc/udev/rules.d/` using your system administrator account and reload udev rules, then reconnect. Do not run the whole application as root. After any failed attempt, unplug and wait for setup to observe that the loader disappeared before reconnecting with D held. The app also remembers interrupted attempts across restarts.

The server binds loopback, checks Host/Origin and requires a session token for mutations. Hosted pages receive no CORS grant. Native URL links carry scenes only; they cannot trigger firmware or RGB writes. There is no automatic flashing, colour application, retry or reconnect replay. No background keystroke recording. Profiles stay in browser storage with a local companion backup. Quit is blocked/deferred during firmware programming. Forced process termination or power loss cannot be made safe by a browser app.

The source export omits owner profiles, photo libraries, research dumps, manufacturer binaries and private Git history. Firmware patch sources are in `firmware/host-rgb`; the pinned patch manifest and hash checks are in `backend/firmware-patch.json` / `backend/firmware.py`. To reproduce images offline: `python3 scripts/prepare_firmware.py /path/to/official.exe --out build/images`. Never flash an arbitrary extraction or rebuild that does not match the pinned hash.

Nuvoton's Apache-2.0 C parser is included only as a RAM-test fixture with its license/notice and provenance. Instrument Sans is included under its OFL license. HIDAPI and the bundled Python/PyInstaller runtime retain their respective licenses. Ducky Lighting is an independent project, not an official Ducky application.
