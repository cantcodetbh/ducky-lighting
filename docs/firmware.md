# Firmware setup

Ducky Lighting uses custom9004 firmware for static RGB, native animations and onboard static colours. Installation and manufacturer V1.10 restoration are available in the companion app on macOS, Windows and Linux.

If the app detects custom9004, no firmware update is needed. Earlier custom9002/9003 firmware still supports its original features; update to add native animations and onboard static saving. Installing firmware resets saved startup colours.

## Compatibility and risk

The supported research target is the **Ducky Mecha Mini DKME2061ST with an M032SE3AE controller**. Check the model label underneath your keyboard. A similar name, case or USB ID does not establish compatibility.

Firmware installation is experimental. Hardware testing is limited to one DKME2061ST on macOS. Physical Windows/Linux flashing remains unverified. A failed or interrupted update can leave the keyboard unusable and may require hardware repair; recovery is not guaranteed.

Use a stable, direct USB connection. Disconnect other Ducky or Nuvoton devices and close other firmware tools. Have another way to type while the keyboard is in bootloader mode.

## Install firmware

1. Open the companion app, then choose **Set up keyboard → Install or restore firmware** from the device menu.
2. Confirm that the underside label reads **DKME2061ST**.
3. Click **Prepare official firmware**. The app downloads Ducky's V1.10 updater, verifies it and prepares the supported images locally. The EXE is never executed. Alternatively, select a local copy of `Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe`.
4. Unplug the keyboard. Hold **D**, reconnect the cable, then release D. Typing and lighting may stop while the bootloader is active.
5. Click **Check bootloader**. The app checks the interface, controller and configuration before allowing installation. This check does not erase flash.
6. Choose **Install custom9004 · RGB, effects and onboard colours**. Read the warning, accept the risk and type **FLASH DKME2061ST**.
7. Click **Erase application and install firmware**. Keep the cable connected and the companion running until the operation finishes.
8. Once all packets are acknowledged, unplug the keyboard and reconnect normally with D released. Check that typing and lighting work, then use **Apply to keyboard** for colours or **Apply effect** for native animations.

Confirmation expires after two minutes. If it expires, repeat the bootloader check.

A completed transfer means the keyboard acknowledged the programming packets. The app cannot verify every programmed byte or confirm that the keyboard has booted; the typing and lighting check is still required.

## If installation fails

The app stops at the first error and does not retry or resume automatically.

Unplug the keyboard and wait until setup no longer detects the bootloader. Reconnect while holding D, release it, then run a fresh check. If the bootloader is still accessible, a separate attempt can restore manufacturer V1.10.

If D-on-connect no longer brings back the bootloader, stop attempting updates. Hardware recovery or repair may be necessary.

## Restore manufacturer firmware

Follow the same preparation and bootloader-check steps, then choose **Restore manufacturer V1.10 · built-in lighting** before confirming installation.

Restoration uses manufacturer V1.10. It is not a backup of the keyboard's previous firmware, including V1.08, and saved keyboard settings may be lost. Browser RGB control will no longer be available after returning to stock firmware.

Restoration has the same interruption risk as installation and is not a guaranteed recovery method.

## Windows

The companion uses the built-in Windows HID driver. A replacement USB driver is not required. Quit an older companion before installing an update.

## Linux permissions

The DEB installs HID permission rules for the normal keyboard and its bootloader. Reconnect the keyboard after installation so the rules take effect.

For the portable archive, open a terminal in the extracted `DuckyLighting` directory and run:

```sh
sudo install -m 0644 70-ducky-lighting.rules /etc/udev/rules.d/70-ducky-lighting.rules
sudo udevadm control --reload-rules
```

Reconnect afterwards. Run the app as your regular desktop user.

The bootloader ID is shared with other Nuvoton devices. The app also checks its report layout, chip ID and configuration before programming.

## Supported updater

Only this official updater is accepted:

```text
Ducky_Mecha_Mini_RGB_V1.10_DKME2061ST.exe
SHA-256: 6d5b1a8fb16c53fc2875dad5399cd574b1fc05eef83141dd89fbcee0ede5aab8
```

A different file or version is rejected. Firmware preparation stays on your computer; the updater is not uploaded to the hosted editor. Manufacturer images are downloaded or supplied at setup time, rather than bundled with the app.

For image hashes, extraction boundaries and protocol details, see [firmware verification](development.md#firmware-verification).

## Colours and effects after installation

Wave, Breathing, Reactive and Ripple run inside the keyboard after Apply effect. Reactive and Ripple use physical keypresses; the companion does not capture typing. Native palettes and timing can differ from the preview.

Save to keyboard stores one static colour frame. It returns after unplugging, even with the companion closed. Save static frame captures a still image when an animated effect is selected; it does not save the animation. After flashing, save your preferred colours again. Select ISO UK for an ISO keyboard so its extra keys are included.
