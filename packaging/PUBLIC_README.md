# Ducky Lighting

An RGB editor for the Ducky Mecha Mini. Set individual key colours, save lighting profiles and preview effects in your browser.

[Open the editor](https://cantcodetbh.github.io/ducky-lighting/) · [Downloads](https://github.com/cantcodetbh/ducky-lighting/releases/tag/v0.4.0-experimental) · [Firmware guide](https://github.com/cantcodetbh/ducky-lighting/blob/main/docs/firmware.md)

## Getting started

1. Download and install the companion app for your computer.
2. Open Ducky Lighting. The editor opens in your default browser.
3. Connect your keyboard and open **Set up keyboard** from the device menu. If custom9002 firmware is already installed, choose your colours and press **Apply to keyboard**.

The companion includes everything needed to run the app. Python and Node.js are only required for development.

| Platform | Download |
|---|---|
| macOS — Apple Silicon | [DMG](https://github.com/cantcodetbh/ducky-lighting/releases/download/v0.4.0-experimental/Ducky-Lighting-macOS-arm64.dmg) |
| macOS — Intel | [DMG](https://github.com/cantcodetbh/ducky-lighting/releases/download/v0.4.0-experimental/Ducky-Lighting-macOS-x64.dmg) |
| Windows — x64 | [Installer](https://github.com/cantcodetbh/ducky-lighting/releases/download/v0.4.0-experimental/Ducky-Lighting-Windows-x64-Setup.exe) |
| Debian / Ubuntu — x64 | [DEB](https://github.com/cantcodetbh/ducky-lighting/releases/download/v0.4.0-experimental/Ducky-Lighting-Linux-x64.deb) |
| Linux — x64 portable | [Archive](https://github.com/cantcodetbh/ducky-lighting/releases/download/v0.4.0-experimental/Ducky-Lighting-Linux-x64.tar.gz) |

The online editor also works on its own for creating and saving profiles. To control a keyboard, select **Connect keyboard** and open the installed companion. Safari and Chromium browsers are supported.

## Lighting controls

- Individual key colours, multi-selection and a drag-to-paint brush.
- Colour picker, HEX values, swatches and brightness controls.
- Static, Spectrum, Breathing, Wave, Reactive and Ripple previews.
- Saved profiles with JSON import and export.
- ANSI US and ISO UK layouts, with Black, Frozen Llama and Creator appearance options.
- Light and dark themes.

**Apply to keyboard** sends the current lighting frame. Animated effects run in the preview; continuous animation on the physical keyboard is not supported yet. Profiles are stored locally.

## Keyboard support

Firmware installation is limited to the **Ducky Mecha Mini DKME2061ST with an M032SE3AE controller**. The edition picker changes the preview only; it does not select different firmware.

RGB control requires custom9002 firmware. Stock firmware does not have a verified RGB control method in this app. Firmware installation and manufacturer V1.10 restoration are available through the companion on macOS, Windows and Linux.

**This is an experimental release.** Hardware testing is limited to one DKME2061ST on macOS. Windows and Linux have passed software and VM tests, but physical USB control and flashing remain unverified on those platforms.

A failed or interrupted firmware update can leave the keyboard unusable and may require hardware repair. Recovery is not guaranteed. Read the [firmware guide](https://github.com/cantcodetbh/ducky-lighting/blob/main/docs/firmware.md) before installing.

Mac downloads are ad-hoc signed and are not notarized. Windows downloads do not have a publisher signature. Your operating system may block these downloads.

## Installation notes

On Mac, drag the app from the DMG into Applications. On Windows, run the installer. When upgrading, quit the existing companion first.

The Linux DEB installs the required HID permissions; reconnect the keyboard afterwards. The portable archive requires [manual permission setup](https://github.com/cantcodetbh/ducky-lighting/blob/main/docs/firmware.md#linux-permissions). Linux builds require glibc 2.35 or later and libudev.

## Development

See [development and testing](https://github.com/cantcodetbh/ducky-lighting/blob/main/docs/development.md) for source builds, the local API and firmware verification details.

For a bug report, include your operating system, companion version, keyboard model and the error shown in the app. [Open an issue](https://github.com/cantcodetbh/ducky-lighting/issues).

Ducky Lighting is an independent project and is not an official Ducky product.
