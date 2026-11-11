# Private mobile setup checklist

- **Status:** Operator checklist for the Castela app layer
- **Date:** 2026-11-11
- **Policy:** [`private-mobile-defaults.md`](private-mobile-defaults.md)
- **Diagnostic:** [`tools/private_defaults_diagnostic.py`](../tools/private_defaults_diagnostic.py)
- **Reference device:** Pixel 9a (`tegu`) on official GrapheneOS

This is a **setup checklist**, not a flashing guide. Install official
GrapheneOS using the official GrapheneOS instructions, keep the bootloader
locked, and install Castela apps from the private channel. Do not root the
device, remount system partitions, or disable verified boot.

If a step needs root, a bootloader unlock, a system-partition write, or a
privileged command, **stop and report it** instead of working around it. The
operator checklist and the diagnostic script never run `sudo`, `pkexec`,
`systemctl`, `pacman`, `mount`, or any other privileged command, and they do not
perform automatic suspend or reboot tests.

## 0. Before touching the device

- [ ] Confirm the device is an officially supported, unlocked, non-carrier-locked
      Pixel that GrapheneOS supports.
- [ ] Confirm the repository and the Castela app build are private.
- [ ] Confirm no signing key, capture, or build artifact is in the checkout.
- [ ] Confirm the app build is a `user` build, not `userdebug` or `eng`.
- [ ] Keep a written record of the GrapheneOS version, Castela app versions, and
      the date of this checklist.

## 1. Base OS and integrity

- [ ] Install the current stable **official GrapheneOS** release.
- [ ] Keep the **bootloader locked**.
- [ ] Confirm **verified boot** reports the normal verified/green state.
- [ ] Confirm **SELinux** is **enforcing**.
- [ ] Confirm the **app sandbox** is active; do not use `android:sharedUserId`,
      root, or a privileged helper.
- [ ] Confirm the hardware-backed keystore/StrongBox and device attestation are
      available; do not replace platform keys.
- [ ] Keep the GrapheneOS updater enabled and current.
- [ ] Do **not** root, unlock the bootloader, flash a custom image, or write to a
      system partition.

Read-only observations that may help; run only if `adb` is already set up and
authorized for this host, then turn USB debugging off again:

```bash
adb shell getprop ro.boot.verifiedbootstate
adb shell getprop ro.boot.flash.locked
adb shell getprop ro.boot.veritymode
adb shell getenforce
adb shell getprop ro.build.type
```

Expected values are a verified/green state, `1` for the locked bootloader,
`enforcing` for verity and SELinux, and `user` for the build type. If a value
does not match, stop and investigate; do not weaken the feature to make it
match.

## 2. Accounts, updates, and telemetry

- [ ] Sign in only to accounts the user actually needs. Prefer no account on a
      dedicated security device.
- [ ] Do not install analytics, crash-reporting, telemetry, or remote-logging
      SDKs in any Castela app. The baseline is **no telemetry** at install and
      no telemetry SDK in any Castela app.
- [ ] Do not enable automatic crash uploads, usage reporting, or "improve the
      product" options.
- [ ] Check the installed package list for unexpected telemetry or remote
      management tools.
- [ ] Keep Castela's own data local. Exported files require an explicit user
      action and a warning.

Record `telemetry.enabled`, `analytics`, `crash_reporting`,
`remote_logging`, and `sdk_packages` in the snapshot. All four booleans are
`false` and the SDK list is empty.

## 3. USB exposure

- [ ] Set USB to **charging-only / no data transfer** for daily use.
- [ ] Turn **USB debugging off** after installation and setup.
- [ ] Revoke old USB debugging authorizations.
- [ ] Leave **USB accessory mode off**.
- [ ] Do not approve an unknown USB host while the device is locked.
- [ ] Use a trusted cable and charger; do not accept data or debugging prompts
      from an untrusted host.

Record `usb.data_enabled`, `usb.debugging_enabled`, and `usb.accessory_mode` as
`false`.

## 4. Wi-Fi exposure

- [ ] Keep Wi-Fi **off at first boot** until a trusted network is chosen.
- [ ] Disable **auto-connect to open networks**.
- [ ] Enable **randomized MAC** per network.
- [ ] Disable **always-available scanning**.
- [ ] Disable **Wi-Fi Direct**.
- [ ] Disable **hotspot/tethering** unless the user explicitly starts it.
- [ ] Remove old open-network profiles and any network the user no longer trusts.
- [ ] Prefer a trusted WPA3/WPA2 network; avoid captive portals for sensitive
      work.
- [ ] Turn Wi-Fi off again when it is not needed for updates.

Record `wifi.enabled` (off at first boot; on is a warning), and record
`auto_connect_open_networks`, `randomized_mac`, `scan_always_available`,
`wifi_direct`, and `hotspot_enabled` in the snapshot.

## 5. Bluetooth and NFC exposure

- [ ] Keep **Bluetooth off** by default.
- [ ] Do not leave the device **discoverable**.
- [ ] Disable **Bluetooth LE scanning** when not in use.
- [ ] Disable **auto-connect** to old or untrusted devices.
- [ ] Keep **NFC off** unless the user has a specific, trusted use.
- [ ] Turn Bluetooth and NFC off again after the task.

Record `bluetooth.enabled`, `discoverable`, `ble_scanning`, `auto_connect`, and
`nfc.enabled` as `false`.

## 6. Permission defaults

- [ ] Confirm permissions are **deny by default**; installing an app grants no
      runtime access.
- [ ] Do not grant `QUERY_ALL_PACKAGES`, `MANAGE_EXTERNAL_STORAGE`,
      `ACCESS_BACKGROUND_LOCATION`, `RECEIVE_BOOT_COMPLETED`,
      `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`, or `SYSTEM_ALERT_WINDOW`.
- [ ] Do not enable accessibility, notification-listener, usage-access, overlay,
      device-admin, or "install unknown apps" access at setup.
- [ ] Do not grant SMS, call-log, phone-state, or contacts access to the
      launcher, theme, setup companion, or security panel.
- [ ] Leave camera and microphone access at **ask** or **deny**.
- [ ] Grant a runtime permission only at the moment of use, with a plain-language
      explanation, and revoke it when the task is done.
- [ ] Use the Storage Access Framework for a user-selected file; do not request
      broad storage access.
- [ ] A live capture is a user-started `VpnService` with a persistent
      notification and a stop control; it never starts at boot.

Record `permissions.default_deny` as `true`, list any user-granted permissions
under `permissions.granted`, and leave `permissions.special_access` empty.

## 7. Lock-screen behaviour

- [ ] Set a **secure lock** (PIN, password, or a strong biometric-backed lock).
- [ ] Set **auto-lock to 30 seconds**, and never more than 60 seconds.
- [ ] Hide **sensitive notification content** on the lock screen.
- [ ] Disable **Quick Settings** on the lock screen.
- [ ] Disable **Smart Lock** and any trusted-place, trusted-device, or
      trusted-face/body unlock.
- [ ] Disable **lock-screen widgets**.
- [ ] Disallow **USB debugging** from the lock screen.
- [ ] Use only the Padilha **wallpaper** on the lock screen. Do not theme the
      lock-screen controls, notifications, font, or security prompts.
- [ ] Do not show personal owner info, capture warnings, or security details on
      the lock screen.

Record the `lock_screen` fields from
[`private-mobile-defaults.md`](private-mobile-defaults.md#6-lock-screen-behaviour).

## 8. Sensor indicators and Padilha UX

- [ ] Keep the **camera indicator** on.
- [ ] Keep the **microphone indicator** on.
- [ ] Do not obscure an indicator with a launcher, wallpaper, panel, overlay, or
      full-screen surface.
- [ ] Keep the **sensor privacy toggle** available.
- [ ] Leave camera and microphone app access at **ask** or **deny**; no standing
      access.
- [ ] Confirm privacy indicators are visible in the Padilha UI.
- [ ] Confirm status meaning uses an icon and text, not colour alone.
- [ ] Check 200% text, TalkBack labels, and reduced motion.
- [ ] Confirm permission, authentication, installer, and lock-screen prompts are
      unmodified platform UI.
- [ ] Confirm dynamic accent changes do not reach privacy indicators or security
      status.

Record the `sensors` and `padilha_ux` fields in the snapshot.

## 9. Telemetry, background work, and offensive tooling

- [ ] Confirm no Castela component has a `BOOT_COMPLETED` receiver.
- [ ] Confirm no always-on background service is installed for Castela.
- [ ] Confirm no periodic job, background sync, or polling loop is enabled.
- [ ] Confirm no analytics, crash-reporting, or remote-logging SDK is present.
- [ ] Confirm no default offensive tooling is installed or started at boot
      (for example an exploit framework, password cracker, or unattended packet
      capture daemon).
- [ ] A lawful diagnostic tool is installed only by the user, started
      explicitly, scoped to a network the user owns or is authorized to test,
      and stopped/cleared afterward.

Record `startup.boot_components`, `startup.background_services`,
`startup.periodic_jobs`, `tooling.offensive_packages`,
`tooling.offensive_binaries`, and `tooling.installed_packages`. The first five
lists are empty.

## 10. Run the diagnostic

- [ ] Generate the snapshot template:

  ```bash
  python3 tools/private_defaults_diagnostic.py --template > private-defaults.json
  ```

- [ ] Replace every template value with the observed device value. Do not leave
      the template's claimed values in place without checking them.
- [ ] Evaluate the snapshot:

  ```bash
  python3 tools/private_defaults_diagnostic.py --input private-defaults.json
  ```

- [ ] Fix every `FAIL`. Review every `WARN`, including Wi-Fi on.
- [ ] Re-run with `--strict` for a release record:

  ```bash
  python3 tools/private_defaults_diagnostic.py --input private-defaults.json --strict
  ```

- [ ] Attach the passing report to the private release record. Do not commit a
      device snapshot that contains personal identifiers.

Expected exit status is `0`. A `1` means the snapshot is not compliant; a `2`
means the JSON is missing, unreadable, or malformed.

## 11. Explicitly not part of this checklist

- [ ] **No automatic suspend or reboot tests.** Do not loop suspend, reboot,
      power-off, or battery-drain operations to test the image.
- [ ] No `sudo`, `pkexec`, `systemctl`, `pacman`, `mount`, or other privileged
      command.
- [ ] No root, bootloader unlock, custom AVB key, system-partition write, or
      SELinux permissive mode.
- [ ] No disabling or bypassing the app sandbox, permission controller, verified
      boot, or GrapheneOS updater.
- [ ] No telemetry "for diagnostics" and no hidden background service.
- [ ] No default offensive tooling at boot.

If a step cannot be completed without one of these, stop and report the blocker.
Do not prompt for a privileged desktop action and do not weaken the device to
make the checklist pass.

## 12. Final verification

- [ ] Boot the device normally and confirm GrapheneOS still reports verified
      boot and enforcing SELinux.
- [ ] Confirm Castela apps open, the launcher works, and the security panel
      starts locked.
- [ ] Confirm no Castela boot receiver, background service, or periodic job
      starts after the reboot.
- [ ] Confirm camera and microphone indicators remain visible.
- [ ] Run the repository tests:

  ```bash
  python3 -m unittest tests.test_private_defaults -v
  bash tests/all.sh
  ```

- [ ] Record the checklist date, device codename, GrapheneOS version, Castela
      app versions, and diagnostic result.
