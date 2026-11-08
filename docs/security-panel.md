# Padilha security panel

- **Status:** Implemented front-end contract and offline preview
- **Date:** 2026-11-08
- **Scope:** Dedicated security surface on the Castela app layer, separate from
  general settings
- **Preview:** [`preview/security/`](../preview/security/index.html)
- **Policy:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md) ·
  [privacy and security-tooling rules](legal/grapheneos-aosp-attribution.md#7-privacy-and-security-tooling-rules)

The security panel is Castela Mobile's exclusive cyber front-end. It is an
ordinary Android app surface backed by public APIs, not a kernel tool, a
baseband monitor, a privileged service, or a replacement for GrapheneOS
verified boot. This document defines the contract implemented by
`preview/security/security-panel.js` and exercised by
`tests/test_security_panel.py`.

## 1. Separation from general settings

The panel has its own registration, route, title, state, and tests. It is not a
section inside general settings, the launcher settings, or a theme screen.

The launcher links to it as its own surface, and the panel declares:

| Field | Value |
| --- | --- |
| Panel id | `com.castela.security` |
| Requires authorized lab mode | Yes |
| Auto-run | No |
| Background scanning | No |
| Hidden service | No |
| Privileged APIs | No |
| Tabs | Network inventory, Capture review, Permission audit, Device integrity |

Registration rejects a panel that claims `autoRun`, `backgroundScanning`,
`hiddenService`, or `privileged`, and rejects a security panel without exactly
the four required tabs or without the lab-mode requirement.

## 2. Authorized lab mode

The panel starts **locked**. Nothing is collected, captured, parsed, or audited
until all of the following are true:

1. The user confirms they own the network or have written permission to inspect
   it.
2. The user presses **Authorize lab mode**. Authorization without that
   acknowledgement is refused with `acknowledgement-required`.
3. The user selects a tab and presses that tab's own action.
4. The tab's local capability is present and not privileged.

Authorization creates an in-memory session and changes the banner to
**Lab mode authorized**. It does **not** start a scan. The banner always carries
the authorized-use warning and a visible **Locked** or **Authorized** state.

**Stop and clear** returns the panel to locked, drops the session, removes
session results, and clears the selected capture filename in the UI. Every run
after that returns `not-authorized` until the user authorizes again.

The session is intentionally in-memory. The preview does not use
`localStorage`, cookies, IndexedDB, or a background service.

## 3. Tabs and missing-tool behaviour

Each tab has a declared capability. Capability detection is a local probe, not
a scan. A missing probe, a false value, an unknown value, or a probe that throws
produces a graceful `unavailable` state with a plain-language reason. The tab
still renders, its action is disabled, and no substitute or privileged provider
is attempted.

| Tab | Capability | Visible to the panel | Not available to the panel |
| --- | --- | --- | --- |
| Network inventory | `networkInventory` | Local interfaces, addresses, link state, DNS settings | Other apps' traffic, kernel sockets, raw packets, baseband |
| Capture review | `captureReview` | A file the user explicitly chooses, reviewed offline | Automatic capture, remote upload, hidden capture service |
| Permission audit | `permissionAudit` | App-visible permission state and explicitly granted usage access | Other users, hidden system packages, privileged policy state |
| Device integrity | `deviceIntegrity` | App signer and configuration facts an ordinary app can read | Verified-boot state, baseband details, kernel attestation |

A missing capability result includes `available: false`, a `reason`, and
`tool: null`. A provider that reports `available: true` together with
`privileged: true` is rejected as `rejected: "privileged-provider"`. A probe
that throws is caught and reported as `rejected: "probe-failed"`; it never
breaks the panel.

## 4. No automatic or hidden work

The front-end and its contract contain:

- no `setInterval`, `setTimeout`, animation loop, worker, or service worker;
- no `fetch`, `XMLHttpRequest`, `WebSocket`, beacon, or remote resource;
- no `VpnService`, root, raw socket, hidden API, or privileged permission;
- no automatic file read, scan, capture, audit, or export;
- no telemetry, analytics, crash-reporting SDK, or background sync.

Capability detection on page load only checks whether an injected local adapter
exists. It does not inspect the network, files, permissions, or device state.

## 5. Data handling

- Captures and inventory results stay in memory for the active session and are
  cleared by **Stop and clear**.
- The preview reads a selected file's name and size only. It does not read file
  contents.
- Packet captures may contain personal data. A visible warning appears in the
  banner and in the capture tab.
- Export is out of scope for this front-end. Any future export must warn before
  writing, use a user-selected destination, and never upload automatically.
- The real app must store sensitive data app-privately and provide a verified
  delete. The panel must not request `MANAGE_EXTERNAL_STORAGE`.

## 6. Registration and test contract

`preview/security/security-panel.js` exports the pure contract:

```js
import {
  PANEL_ID,
  PANEL_TABS,
  createPanelRegistry,
  createSecurityPanel,
  registerSecurityPanel,
} from "./security-panel.js";

const registry = createPanelRegistry();
const definition = registerSecurityPanel(registry); // com.castela.security
const panel = createSecurityPanel({ definition, probe: {} });

panel.snapshot().labMode; // "locked"
panel.run("network").code; // "not-authorized"
panel.authorize({ acknowledged: true });
panel.run("network").code; // "capability-unavailable" with an empty probe
panel.stopAndClear().cleared; // true
```

Optional local adapters are injected as `globalThis.CASTELA_SECURITY_TOOLS`;
each key is a function that returns `true` or an object such as
`{ available: true, tool: "local-inventory", version: "1.0" }`. Supplying an
adapter only makes the capability detectable. It still does not run until the
user authorizes lab mode and presses the tab action.

Tests cover:

- panel registration, duplicate registration, and the required four tabs;
- authorization refusal without acknowledgement, explicit authorization,
  no auto-run, and stop/clear revocation;
- missing, false, privileged, and throwing capability probes;
- no timers, network calls, remote resources, workers, or automatic actions in
  the panel source.

Run the focused test and then the repository suite:

```bash
python3 -m unittest tests.test_security_panel -v
bash tests/all.sh
```

## 7. Android build boundary

The preview is HTML/CSS/JavaScript because this repository does not contain a
Gradle project or Android SDK. A future signed APK must preserve the same
contract using public Android APIs:

- `ConnectivityManager`/`LinkProperties` for app-visible network facts;
- `VpnService` only for a user-started capture, with a persistent notification
  and a stop control;
- Storage Access Framework for user-selected capture files;
- `PackageManager` and user-granted `UsageStatsManager` access for audits;
- `PackageManager` signing information for app-level integrity facts.

The panel must not request root, raw sockets, `QUERY_ALL_PACKAGES`,
`MANAGE_EXTERNAL_STORAGE`, privileged permissions, `android:sharedUserId`, or a
hidden background service. It must not imply kernel, baseband, or verified-boot
visibility it does not have.

If a future requirement needs privileged APIs, raw sockets, kernel/eBPF
visibility, or preinstalled system components, that is a new architecture
decision under ADR 0001's revisit triggers, not a change to this panel.

## 8. Known limits

- This is a front-end contract and offline preview, not a signed Android app or
  a claim that a device has been instrumented.
- The preview has no real network inventory, capture parser, permission source,
  or integrity verifier; those appear as explicit missing-tool states.
- GrapheneOS remains responsible for verified boot, OS updates, and system
  security. The panel does not change them.
