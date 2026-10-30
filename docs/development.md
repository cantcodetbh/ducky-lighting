# Development

Ducky Lighting uses TypeScript and SVG for the editor, a Python local service, an IOKit adapter on macOS and HIDAPI on Windows/Linux. The companion bundles the frontend, Python runtime and USB libraries.

## Requirements

- Node.js 22 and Python 3.11.
- macOS: Xcode command-line tools.
- Windows installer builds: NSIS.
- Firmware simulation tests: Clang or GCC.
- Linux installer builds: dpkg-deb, libudev and a C compiler. The packages target x64 systems with glibc 2.35 or later.

## Run from source

Create a Python virtual environment and install the packaging dependencies:

```sh
npm ci
python3 -m venv .venv-release
.venv-release/bin/python -m pip install -r packaging/requirements.txt
npm run build
```

On macOS, build the IOKit helpers:

```sh
.venv-release/bin/python scripts/build_native.py
```

Start the local editor:

```sh
.venv-release/bin/python companion.py
```

On Windows, use `.venv-release\Scripts\python` in place of `.venv-release/bin/python`, and `python` when creating the environment.

The service listens on `127.0.0.1:8770`. For frontend development, `npm run dev` starts Vite on port 5178 and proxies API requests to the local service.

## Tests and installers

```sh
npm test
.venv-release/bin/python scripts/test_firmware.py
.venv-release/bin/python scripts/build_installers.py
```

`npm test` uses the `python3` command. On Windows systems without that alias, run the test suites separately:

```powershell
npx tsx --test tests/state.test.ts
.venv-release\Scripts\python -m unittest discover -s tests -p "test_*.py"
```

Browser tests require the app running on port 8770:

```sh
npx playwright install chromium webkit
npm run test:browser
npm run test:theme
node tests/setup.mjs
```

The manual GitHub Actions workflow builds Apple Silicon Mac, Intel Mac, Windows x64 and Ubuntu x64 installers. It checks installed runtimes, the packaged firmware helper and uninstall behaviour. `scripts/verify_installers.py` runs only on disposable CI runners because it installs and removes packages.

Firmware tests use synthetic images and RAM-backed device fixtures. The Nuvoton C parser tests cover 90 failure scenarios; portable transport tests cover framing, image streams, connection handling and error stops. Passing these tests does not establish physical USB compatibility. Windows/Linux control and flashing still require real-device validation.

## Project structure

| Location | Contents |
|---|---|
| `src/components/` | Editor components and SVG rendering |
| `src/data/` | Keyboard layouts and appearance definitions |
| `src/state.ts`, `src/effects.ts` | Profiles, scene validation and preview effects |
| `backend/server.py` | Local API, static assets and profile storage |
| `backend/hardware.py` | RGB adapter selection and key-to-LED mapping |
| `backend/firmware.py` | Image preparation, confirmation and update coordination |
| `backend/firmware_hid.py`, `backend/firmware_ipc.py` | Portable firmware transport and worker communication |
| `backend/native/` | macOS IOKit helpers |
| `firmware/effects-rgb/` | Current custom9004 sources (native effects and onboard static journal) |
| `packaging/` | App bundles, installers and platform resources |

## Local API and storage

The API binds to loopback, validates Host and Origin, and requires a session token for writes. Hosted pages do not receive CORS access to the service. Companion links carry a preview scene and cannot start an RGB or firmware operation.

RGB changes require an explicit Apply action. Reconnection does not replay a frame. Firmware programming requires the supported image, a matching bootloader check, a one-use confirmation plan and typed confirmation. Failed transfers stop without automatic retry or resume.

Profiles are stored in browser storage with a companion backup. Packaged app data lives in:

| System | Directory |
|---|---|
| macOS | `~/Library/Application Support/Ducky Lighting` |
| Windows | `%LOCALAPPDATA%\Ducky Lighting` |
| Linux | `$XDG_DATA_HOME/ducky-lighting`, or `~/.local/share/ducky-lighting` |

Source builds use the project's `data/` directory. Firmware attempt logs are stored alongside locally prepared images. A transfer's final state is `acknowledged`, rather than verified flash contents or a confirmed boot.

## Firmware verification

The accepted official V1.10 updater has SHA-256:

```text
6d5b1a8fb16c53fc2875dad5399cd574b1fc05eef83141dd89fbcee0ede5aab8
```

Preparation extracts offsets `0x20F0B8..0x21EA20` (63,848 bytes) and checks the following length word. It verifies patch anchors, preserves the vector table and checks the complete resulting image hash.

| Image | SHA-256 |
|---|---|
| Manufacturer V1.10 | `fb29585b17a0ee1883287def35a1b107695a13c4dc85355cb27f54921ea5f514` |
| Custom9004 (131072 bytes) | `cc1c222b7a5bb03866c5a1baa57e7587fc214596ed9b271b4f27410332d43d43` |

Reproduce preparation offline with a local updater:

```sh
python3 scripts/prepare_firmware.py /path/to/official.exe --out build/images
```

The bootloader check requires one matching 0416:3F00 interface, the supported report layout, PDID `0x01132E10` and the measured configuration words. The programming sequence targets APROM offset zero, with a 48-byte first payload and 56-byte continuations. There is no configuration-write, bootloader-update, unlock or arbitrary packet endpoint.

Windows/Linux retain one open handle from inspection through confirmation. The helper checks the image before programming and never reopens the device after a disconnection. Linux uses hidraw with the installed udev rules; Windows uses its HID driver and validates reconstructed report layouts. macOS uses the IOKit helper and checks registry identity and location before each report.

Each reply must pass checksum and sequence checks. The 16-bit checksum can miss equal-sum corruption; the app does not have complete flash readback. Interrupted-flash recovery is unproven. Current physical testing is limited to one DKME2061ST/M032SE3AE on macOS, and the current update flow still needs physical validation.

## Third-party software

The Nuvoton C parser is an Apache-2.0 test fixture with its [licence](../tests/firmware-fixture/Nuvoton-LICENSE), [notice](../tests/firmware-fixture/Nuvoton-NOTICE) and [provenance](../tests/firmware-fixture/provenance.json). Instrument Sans is distributed under its [OFL licence](../src/assets/Instrument-Sans-OFL.txt). HIDAPI, Python and PyInstaller retain their respective licences.

### Native effects and onboard colours

The typed API adds POST `/api/effect` (`effect`, `speed`, `colour`, `device_id`, `consent`), POST `/api/onboard/save` (a complete `layout`/`colours` frame plus `device_id`/`consent`) and POST `/api/onboard/clear` (`device_id`/`consent`). Host/Origin/token checks apply. No generic report or arbitrary-memory endpoint is exposed.

Custom9004 accepts D1 operation6 with original renderer mode1/4/6/8, bounded speed1–10 and RGB8. Operation4 saves a static frame;5 clears it. The 240-byte CRC32/commit-last record alternates between reserved APROM pages0x1FC00 and0x1FE00, with the previous valid record retained while writing. Flash operations run from SRAM. Clear and identical-save paths are covered by offline tests; physical interrupted-save recovery is not established. A complete firmware installation initializes these pages and clears saved colours.

Source builds can reproduce the candidate using `scripts/effects/build_candidate.py` with the exact official updater. It needs Apple clang, pyelftools, Capstone and ziglang/LLD. `scripts/effects/validate_arm.py` and `validate_effects.py` use Unicorn to execute the compiled firmware and native renderers offline. Installer users do not need these tools: preparation applies the published fixed patch locally and checks the exact resulting SHA-256.

Static saving/restoration and all four native effects were physically verified on one DKME2061ST using macOS. The effect path does not stream frames or capture host keypresses. Only static colours persist across power removal in this release. Windows/Linux physical USB operation and interrupted-flash recovery remain unverified.
