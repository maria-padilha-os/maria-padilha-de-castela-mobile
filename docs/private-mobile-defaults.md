# Private mobile defaults

- **Status:** Implemented policy, setup checklist, and read-only diagnostic
- **Date:** 2026-11-11
- **Scope:** The Castela app layer on official GrapheneOS
- **Checklist:** [`setup-checklist.md`](setup-checklist.md)
- **Diagnostic:** [`tools/private_defaults_diagnostic.py`](../tools/private_defaults_diagnostic.py)
- **Tests:** [`tests/test_private_defaults.py`](../tests/test_private_defaults.py)
- **Decision record:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- **Related:** [security panel](security-panel.md) ·
  [overlay and build boundaries](branding/overlay-and-build.md) ·
  [privacy and security-tooling rules](legal/grapheneos-aosp-attribution.md#7-privacy-and-security-tooling-rules)

This document defines the conservative, private, battery-safe baseline for a
Castela Mobile installation. It is a policy for the app layer and for the
device settings the user is asked to review. It is **not** a system image, a
ROM build, a flashing procedure, or authorization to modify a system partition.

The baseline is deliberately small:

- **no telemetry** and no analytics, crash-reporting, or remote-logging SDK;
- **no unnecessary background services**, boot receivers, or periodic jobs;
- **no default offensive tooling** at boot;
- conservative permission defaults and radio exposure;
- a lockscreen that does not leak content or expose controls;
- camera and microphone indicators that cannot be hidden by the theme;
- GrapheneOS verified boot, SELinux, and the app sandbox left untouched.

The **[private mobile setup checklist](setup-checklist.md)** turns this policy
into operator steps. The **read-only diagnostic script** evaluates a JSON
snapshot of observed values. Neither one runs a privileged command. **No automatic suspend or reboot tests** are part of this repository, the checklist,
or the diagnostic script.

## 1. What the baseline covers

| Area | Default state | Enforcement |
| --- | --- | --- |
| Telemetry | Off; no analytics, crash reporting, remote logging, or telemetry SDK | Diagnostic fails on any enabled field or SDK package |
| Background work | No Castela boot receiver, always-on background service, or periodic job | Diagnostic fails on any startup entry |
| Offensive tooling | None installed or started at boot | Diagnostic fails on explicit tools and known package markers |
| Permissions | Deny by default; request at the moment of use | Diagnostic fails on deny-by-default grants and special access |
| USB | Charging-only; data, debugging, and accessory modes off | Diagnostic fails on any enabled exposure |
| Wi-Fi | Off at first boot; no open-network auto-connect, randomized MAC, no always-on scanning | Wi-Fi on is a warning; unsafe exposure settings fail |
| Bluetooth / NFC | Off; not discoverable, not scanning, no auto-connect | Diagnostic fails on enabled radios and exposure modes |
| Lock screen | Secure lock, auto-lock within 60 seconds, sensitive content hidden, quick settings and trust agents off | Diagnostic fails on each unsafe setting |
| Sensors | Camera and microphone indicators on and unobscured; access asks first | Diagnostic fails on hidden indicators or standing access |
| Padilha UX | Privacy indicators visible, status not colour-only, 200% text, TalkBack labels, reduced motion, wallpaper-only lock-screen branding | Diagnostic fails on a UX regression |

"Off at first boot" describes the setup baseline. A user may later enable Wi-Fi
or Bluetooth for a specific task. The diagnostic reports Wi-Fi on as a warning
and Bluetooth on as a failure because Bluetooth is unnecessary for setup and
has a larger passive-exposure surface. Re-run the baseline after returning the
device to its conservative state.

## 2. GrapheneOS security features that must remain untouched

GrapheneOS owns the operating system, firmware, kernel, verified boot, and
update chain. Castela is an independent app layer. The following features are
**not** Castela settings and must not be disabled, replaced, bypassed, or
weakened by an app, theme, overlay, diagnostic, or checklist step:

| GrapheneOS feature | Why it must remain untouched | Castela boundary |
| --- | --- | --- |
| Verified boot / Android Verified Boot (AVB) and a locked bootloader | Establishes the trust root for the OS and detects unauthorized system modification | Castela never flashes, roots, unlocks, re-signs, or patches the boot chain |
| Hardware-backed keystore, StrongBox, and key attestation | Protects app and device keys and supports integrity statements | Castela uses ordinary app signing; it does not replace or export platform keys |
| SELinux in enforcing mode | Confines processes and limits the impact of a compromised app or service | Castela never sets permissive mode, loads a custom policy, or asks for a privileged domain |
| Android app sandbox, per-app UID, scoped storage, and `android:sharedUserId` prohibition | Keeps each app's data and capabilities separate | Castela apps are separate packages with separate keys; no shared UID |
| Per-app network and sensor permissions, including GrapheneOS network/sensors toggles | Lets the user revoke network or sensor access per app | Castela does not add a bypass, proxy, or hidden privileged service |
| Hardened memory allocator, MTE where supported, and exploit mitigations | Raise the cost of memory-corruption exploitation | Castela does not ship native libraries that opt out or disable them |
| GrapheneOS updater and signed OS update channel | Delivers firmware, kernel, and OS security fixes | Castela never proxies, mirrors, or re-signs OS updates |
| Secure lock screen, duress PIN/password, and auto-reboot | Protects a locked device and limits forensic exposure | Castela may supply wallpaper only; it does not theme or weaken the lock screen |
| USB-C port control and USB peripheral policy | Limits DMA, accessory, and debugging exposure | Castela does not request USB host/accessory access at boot |
| Package installer, permission controller, and security-critical UI | These surfaces make security decisions the user must be able to trust | Castela never overlays, restyles, or intercepts them |

**Do not weaken verified boot, SELinux, or app sandboxing.** If a task appears
to require root, a bootloader unlock, a system-partition write, an SELinux
change, a privileged permission, `android:sharedUserId`, or a hidden system
service, stop. That is a new architecture decision under ADR 0001, not a
configuration change to this baseline.

## 3. Boot-time policy: no telemetry, no unnecessary services, no offensive tooling

The baseline treats the following as unnecessary for a Castela app layer:

| Prohibited at boot | Why | Allowed alternative |
| --- | --- | --- |
| `BOOT_COMPLETED` receivers and other boot components | Start work without a current user action and consume battery | Start only when the user opens the app or presses an action |
| Always-on background services | Keep a process and radio/sensor alive when nothing is in use | A user-started foreground service with a persistent notification, such as an explicit `VpnService` capture |
| Periodic jobs, background sync, and polling | Wake the device and create a recurring privacy surface | Explicit refresh, or an OS-owned updater outside Castela |
| Telemetry, analytics, crash reporting, and remote logging SDKs | Send data off the device and create a persistent network surface | Local logs the user can choose to export; no automatic upload |
| Default network scanners, exploit frameworks, password crackers, and packet-capture daemons | Turn a private phone into an unattended attack platform | A user-installed tool that the user starts explicitly, subject to local law and authorization |

The startup lists in the diagnostic snapshot cover **Castela and user-installed
components**, not GrapheneOS's own core services. Do not disable GrapheneOS
system services to make the diagnostic pass. The goal is to keep the app layer
from adding hidden work, not to strip the operating system.

The [security panel](security-panel.md), its
[local-network inventory](local-network-inventory.md), and its
[pcap capture/review](pcap-capture-review.md) extension follow the same rule:
they start locked, do nothing on construction or first launch, and require an
explicit user action. Live capture is a user-started foreground service with a
persistent indicator; it is not a boot service.

## 4. Permission defaults

The default is **deny**, and a permission is requested only when the user is
about to use the feature that needs it. Installation alone grants nothing.

| Permission or access | Default | Rule |
| --- | --- | --- |
| `QUERY_ALL_PACKAGES` | Denied | Use `LauncherApps` and explicit package queries |
| `MANAGE_EXTERNAL_STORAGE` | Denied | Use the Storage Access Framework for user-selected files |
| `ACCESS_BACKGROUND_LOCATION` | Denied | No background location; request foreground location only for an explicit action |
| `RECEIVE_BOOT_COMPLETED` | Denied | No boot receivers |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | Denied | No exemption request; design for Doze and battery limits |
| `SYSTEM_ALERT_WINDOW` | Denied | No overlays over other apps or security UI |
| Accessibility, notification-listener, and usage-access services | Denied until explicitly granted for a user-started audit | Never enable at install or boot |
| SMS, call log, phone state, and contacts | Denied | Not needed by the launcher, theme, setup, or panel |
| `CAMERA` and `RECORD_AUDIO` | Denied at install; ask at use | No standing sensor access and no background capture |
| `VpnService` | User-started only | Foreground service, persistent notification, visible stop control |
| Internet | App-specific and minimal | No telemetry; offline review and local inventory work without upload |

Special access is not a shortcut around the runtime permission model. The
diagnostic fails if `default_deny` is false, if a deny-by-default permission is
already granted, or if any special-access entry is present in the baseline
snapshot. A user-granted permission for an explicit task is recorded separately
and re-reviewed, not silently treated as a default.

## 5. USB, Wi-Fi, Bluetooth, and NFC exposure

Radios and ports are attack surface and battery load. The baseline keeps them
quiet until the user needs them.

### USB

| Setting | Baseline | Reason |
| --- | --- | --- |
| USB data | Off; charging-only | Prevents a connected host from presenting storage or a data interface |
| USB debugging | Off after setup | Removes the ADB host trust path from daily use |
| USB accessory mode | Off | No implicit accessory or host role |
| USB debugging authorizations | Revoked after setup | An old host key must not remain trusted |
| New USB device prompts | Reviewed while unlocked | Do not approve an unknown host on a locked screen |

### Wi-Fi

| Setting | Baseline | Reason |
| --- | --- | --- |
| Wi-Fi radio | Off at first boot | Reduce passive exposure and battery use until a trusted network is chosen |
| Auto-connect to open networks | Off | Prevents association with an unauthenticated access point |
| Randomized MAC per network | On | Limits tracking across networks |
| Always-available scanning | Off | Stops background scanning when Wi-Fi is off |
| Wi-Fi Direct | Off | Removes an unnecessary peer-to-peer surface |
| Hotspot / tethering | Off | No unintended network bridge |
| Saved open networks | None | Remove old open-network profiles |

Wi-Fi on is a **warning** in the diagnostic because a user may need it for OS
and app updates. The unsafe settings above are failures even when Wi-Fi is on.

### Bluetooth and NFC

| Setting | Baseline | Reason |
| --- | --- | --- |
| Bluetooth radio | Off | Reduces passive radio exposure and idle battery use |
| Discoverable mode | Off | Prevents unsolicited pairing |
| Bluetooth LE scanning | Off | Stops background scanning |
| Auto-connect to known devices | Off | No silent connection to an old or spoofed device |
| NFC | Off | Removes an unnecessary tap-and-pay/read surface |

A user who needs Bluetooth turns it on for that task and turns it off afterward.
The baseline does not pair devices automatically or keep a discoverable window
open.

## 6. Lock-screen behaviour

The lock screen is a security boundary. Padilha may provide the wallpaper, but
it must not change the meaning of a lock-screen control, hide a warning, or make
sensitive content readable without authentication.

| Setting | Baseline | Reason |
| --- | --- | --- |
| Secure lock | On | A swipe-only lock is not a security boundary |
| Auto-lock | 30 seconds, never more than 60 | Shortens the unlocked window |
| Sensitive notification content | Hidden | Prevents messages, codes, and capture alerts from appearing on the lock screen |
| Quick Settings on the lock screen | Off | Prevents radio, network, and device-control changes without unlocking |
| Smart Lock / trust agents | Off | No trusted place, device, or face/body bypass |
| Lock-screen widgets | Off | No unauthenticated content surface |
| USB debugging from the lock screen | Disallowed | No host trust path while locked |
| Lock-screen branding | Wallpaper only | No system UI, font, icon, or security-prompt theming |

The [overlay and build boundaries](branding/overlay-and-build.md) already state
that the lock screen is out of scope for app-layer theming. This baseline makes
that explicit: a Padilha wallpaper is allowed; a Padilha lock-screen control,
notification treatment, or security prompt is not.

## 7. Sensor indicators and Padilha UX

GrapheneOS shows camera and microphone indicators when an app uses a sensor.
Those indicators are security-critical UI. They must remain visible, legible,
and above the app surface.

| Requirement | Baseline | Padilha UX review |
| --- | --- | --- |
| Camera indicator | On | Visible in the status area and not covered by a launcher, panel, or overlay |
| Microphone indicator | On | Visible in the status area and not covered by a launcher, panel, or overlay |
| Indicator obscuring | Forbidden | A theme, wallpaper, or full-screen surface must not hide or recolour an indicator into the background |
| Sensor privacy toggle | Available | The user can revoke camera/microphone access without uninstalling an app |
| Camera/microphone app access | Ask or deny | No standing access; the indicator appears whenever access is active |
| Privacy indicators in the Padilha UI | Visible | The launcher and security panel show the same privacy state the OS shows |
| Status meaning | Icon plus text, never colour alone | Padilha status colours follow the WCAG 2.2 AA pairs in `tokens.json` |
| Text and accessibility | 200% text, TalkBack labels, reduced motion | The theme must not trade legibility for brand |
| Security prompts | Unmodified | Permission, authentication, installer, and lock-screen prompts keep the platform presentation |

The visual review is deliberately conservative:

- Padilha colours may style Castela content, but success, warning, and danger
  states keep an icon and a text label in addition to colour.
- The security panel's warnings, lab-mode banner, capture indicator, and
  stop/clear controls use the Padilha palette only through tested contrast
  tokens. They do not become low-contrast decoration.
- The lock screen receives the wallpaper only. No Padilha widget, quick action,
  notification summary, or replacement clock is part of this baseline.
- A dynamic accent may tint Castela accents; it cannot tint privacy indicators,
  permission prompts, or security status semantics.

## 8. Diagnostic script

The diagnostic is a pure evaluator. It reads JSON from a file or stdin and
writes a report to stdout. It does not call `adb`, open a socket, start or stop a
service, change a setting, suspend, reboot, mount, or write outside the
checkout.

```bash
# Print a compliant schema to fill in with observed values.
python3 tools/private_defaults_diagnostic.py --template > private-defaults.json

# Evaluate a completed snapshot.
python3 tools/private_defaults_diagnostic.py --input private-defaults.json

# Machine-readable output for a release record.
python3 tools/private_defaults_diagnostic.py --input private-defaults.json --json

# Treat warnings, including Wi-Fi on, as failures.
python3 tools/private_defaults_diagnostic.py --input private-defaults.json --strict

# Read a snapshot from stdin.
cat private-defaults.json | python3 tools/private_defaults_diagnostic.py
```

Exit status:

| Status | Meaning |
| --- | --- |
| `0` | No failure. Warnings may be present; `--strict` makes them fail |
| `1` | At least one failure, or a warning under `--strict` |
| `2` | Missing, unreadable, or malformed JSON, or a non-object snapshot |

The template is a **claim**, not proof. The script cannot see the device. The
operator fills each value from the Settings UI or a read-only observation, then
runs the script. A passing report means the snapshot matches the policy; it does
not attest the hardware or replace GrapheneOS verified boot.

### Snapshot sections

| Section | Fields checked |
| --- | --- |
| `device` | `grapheneos`, `build_type` (`user`) |
| `security` | `bootloader_locked`, `verified_boot` (`green`), `selinux` (`enforcing`), `app_sandbox`, `hardware_keystore` |
| `telemetry` | `enabled`, `analytics`, `crash_reporting`, `remote_logging`, `sdk_packages` |
| `startup` | `boot_components`, `background_services`, `periodic_jobs` |
| `tooling` | `offensive_packages`, `offensive_binaries`, `installed_packages` |
| `permissions` | `default_deny`, `granted`, `special_access` |
| `usb` | `data_enabled`, `debugging_enabled`, `accessory_mode` |
| `wifi` | `enabled` (warning), `auto_connect_open_networks`, `randomized_mac`, `scan_always_available`, `wifi_direct`, `hotspot_enabled` |
| `bluetooth` | `enabled`, `discoverable`, `ble_scanning`, `auto_connect` |
| `nfc` | `enabled` |
| `lock_screen` | `secure_lock`, `auto_lock_seconds`, `hide_sensitive_notifications`, `quick_settings_enabled`, `smart_lock`, `lock_screen_widgets`, `usb_debugging_allowed` |
| `sensors` | `camera_indicator`, `microphone_indicator`, `indicators_obscured`, `sensor_privacy_toggle`, `camera_access`, `microphone_access` |
| `padilha_ux` | `privacy_indicators_visible`, `status_not_color_only`, `text_scale_200`, `talkback_labels`, `reduced_motion`, `lock_screen_branding`, `security_prompts_unmodified` |

Missing privacy or security fields fail closed. Do not "fix" a failure by
deleting the field, and do not disable a check to make the report pass.

## 9. Verification and change control

Run the focused test and the repository suite:

```bash
python3 -m unittest tests.test_private_defaults -v
bash tests/all.sh
```

The tests cover a compliant baseline, fail-closed security invariants, telemetry
and background work, offensive tooling, permission defaults, USB, Wi-Fi,
Bluetooth, and NFC exposure, lock-screen behaviour, sensor indicators, Padilha UX
review fields, the CLI exit codes, and the diagnostic's no-device/no-network
source boundary.

Changes to this baseline must update the policy, the setup checklist, the
diagnostic schema, and the tests together. A change that needs a privileged
component, a system-image modification, or a weakened OS security feature
requires a new ADR and cannot be merged as a default tweak.

## 10. References

- GrapheneOS: <https://grapheneos.org/>
- GrapheneOS usage and security features: <https://grapheneos.org/usage>
- GrapheneOS FAQ: <https://grapheneos.org/faq>
- GrapheneOS releases: <https://grapheneos.org/releases>
- Android permissions: <https://developer.android.com/guide/topics/permissions/overview>
- Android security best practices: <https://developer.android.com/privacy-and-security/security-best-practices>
- WCAG 2.2: <https://www.w3.org/TR/WCAG22/>
