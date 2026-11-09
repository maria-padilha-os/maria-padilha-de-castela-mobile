# Local-network inventory extension

- **Status:** Implemented front-end contract, offline preview wiring, and explicit
  Termux/native helper
- **Date:** 2026-11-09
- **Scope:** The Network inventory tab of the
  [Padilha security panel](security-panel.md)
- **Contract:** [`preview/security/network-inventory.js`](../preview/security/network-inventory.js)
- **Helper:** [`tools/network_inventory_helper.py`](../tools/network_inventory_helper.py)
- **Policy:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md) ·
  [privacy and security-tooling rules](legal/grapheneos-aosp-attribution.md#7-privacy-and-security-tooling-rules)

The inventory is a defensive lab tool for the network the user owns or is
authorized to test. It is an ordinary app surface plus an optional explicit
Termux/native helper. It is **not** a packet sniper, a port scanner, an exploit
framework, or a credential collector. Its contract id is
`com.castela.network-inventory`; it performs no credential capture.

## 1. What it does

The inventory displays three things per device:

| Field | Source | Notes |
| --- | --- | --- |
| Host | Provider-observed hostname | Falls back to `Unknown host`; control characters are removed |
| Address | Provider-observed IPv4/IPv6 address | Must be private, link-local, or loopback **and** inside the validated target |
| Service hints | Static catalog plus provider observations | Hints only; no active probing |

A result is only stored after a user authorized lab mode and pressed the
**Start local inventory** action. Construction of the contract does not run a
provider, read a file, touch a socket, or start a timer.

## 2. Authorization is mandatory

The panel starts locked. The user must confirm the statement:

> I own or am authorized to test this network, and I will inspect only devices I
> am permitted to test.

Then the user presses **Authorize lab mode**. Authorization without the
acknowledgement fails with `acknowledgement-required`. Even after authorization,
nothing runs until the user presses the inventory action for a validated range.

**Stop and clear** revokes the session and removes in-memory results. Every run
after that returns `not-authorized` until the user authorizes again.

## 3. Range policy

Only private, link-local, and loopback ranges are accepted. Public ranges are
rejected before the provider is called. Ranges that cross a private/public
boundary are rejected as a whole, so `192.168.0.0/15` and `10.0.0.0/7` cannot be
used to reach public space.

| Family | Accepted scopes | Rejected by default |
| --- | --- | --- |
| IPv4 | `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16` (private); `169.254.0.0/16` (link-local); `127.0.0.0/8` (loopback) | Public, shared (`100.64.0.0/10`), documentation, benchmarking, reserved, multicast, unspecified |
| IPv6 | `fc00::/7` (ULA); `fe80::/10` (link-local); `::1/128` (loopback) | Global unicast, documentation, site-local, multicast, unspecified |

Defensive size limits keep a typo from turning into a sweep:

- IPv4 targets are capped at 1024 addresses (`/22` or narrower).
- IPv6 targets are capped at `/64` or narrower.
- Results are capped at 512 hosts, with truncation reported in the UI.
- IPv6 inventory is a neighbor-table/advertisement scope, not a sweep of every
  address in the prefix.

Host bits in a typed target are normalized to the network address. For example,
`192.168.1.50/24` becomes `192.168.1.0/24`.

## 4. Discovery providers

The pure contract never performs discovery itself. A provider must be injected
explicitly. The accepted kinds are:

| Kind | Use |
| --- | --- |
| `android-public-api` | `ConnectivityManager`, `LinkProperties`, and `NsdManager` facts an ordinary Android app may read after user action |
| `termux-helper` | An explicit user-installed helper, such as the non-privileged `ip -j neigh` reader in `tools/network_inventory_helper.py` |
| `fixture` | Tests and offline previews; never presented as live discovery |

A provider is an object with a `kind`, an optional `label`, and a synchronous
`discover(context)`, `inventory(context)`, or `scan(context)` function. The
provider receives the validated target and a session id, never credentials.

The contract refuses a provider that declares any of these flags as `true`:

`privileged`, `root`, `requiresRoot`, `usesRoot`, `rawSockets`, `rawSocket`,
`credentialCapture`, `credentialHarvesting`, `bruteForce`, `exploit`,
`packetCapture`, `vpnService`, `hiddenService`.

An unapproved kind is rejected with `unapproved-provider`. A missing provider is
a normal `provider-missing` state, not a crash. A provider exception is caught
and reported as `scan-failed`; it never escapes the panel.

### Termux/native helper

The helper reads the neighbor cache explicitly, not by scanning:

```bash
ip -j neigh | python3 tools/network_inventory_helper.py --target 192.168.1.0/24
```

It reads only address and state fields, drops failed/incomplete entries, removes
MAC addresses, and never emits credentials. The app-side contract validates the
helper output again, so a malicious helper cannot inject a public address or a
credential field into the display. The helper uses no root, no raw socket, no
packet capture, and no subprocess call of its own.

A native/Termux adapter can hand validated helper JSON to the preview as a
provider. The provider remains the explicit trust boundary:

```js
globalThis.CASTELA_NETWORK_PROVIDER = {
  kind: "termux-helper",
  label: "Termux ip-neigh helper",
  discover: () => JSON.parse(helperOutput),
};
```

The preview does not fetch that output itself. The user or host app supplies it.

## 5. Service hints without exploitation

The service hints come from a static catalog keyed by observed port, plus the
provider's observed service list. The inventory does not:

- sweep address space or connect to every port;
- grab banners, certificates, or HTTP headers;
- brute-force credentials or authentication;
- exploit a service, run a vulnerability check, or download a payload;
- capture usernames, passwords, tokens, cookies, or private keys.

Provider fields other than `hostname`/`host`/`name`, `address`/`ip`/`addresses`,
and `services`/`openPorts`/`ports` are discarded. In particular, any
`password`, `credential`, `token`, `banner`, or similar field is never copied
into a result, a snapshot, or the DOM.

## 6. Data handling

- Results live in memory for the active session only.
- The preview uses no `localStorage`, cookies, IndexedDB, service worker, or
  background service.
- **Stop and clear** removes the session, target, and results, and clears the
  range field.
- No telemetry, analytics, upload, remote font, remote script, or network
  request is made by the panel.
- The helper writes to stdout only when the user runs it; it does not write
  inventory files.

## 7. Tests and fixtures

Tests use fixture provider data. There is **no live scan** in CI; tests never
need a device, network, root, or Termux.

Covered cases include:

- private, link-local, loopback, ULA, and IPv6 link-local targets accepted;
- public, shared, documentation, multicast, unspecified, and mixed-boundary
  ranges rejected with a specific code;
- oversized IPv4 and IPv6 targets rejected;
- no provider call before authorization, and no call after **Stop and clear**;
- public, out-of-range, malformed, and duplicate hosts filtered;
- public host addresses and credential-like fields never displayed;
- provider flags and unapproved kinds rejected;
- provider exceptions and invalid results handled gracefully;
- the Python helper's fixture parsing, filtering, and public-range refusal.

Run the focused tests and then the repository suite:

```bash
python3 -m unittest tests.test_network_inventory -v
bash tests/all.sh
```

## 8. Android build boundary

The preview is HTML/CSS/JavaScript because this repository does not contain a
Gradle project or Android SDK. A future signed APK must preserve the same
contract using public Android APIs. It must not request root, raw sockets,
`QUERY_ALL_PACKAGES`, `MANAGE_EXTERNAL_STORAGE`, privileged permissions,
`android:sharedUserId`, or a hidden background service. It must not imply
kernel, baseband, or verified-boot visibility it does not have.

If a future requirement needs raw packets, kernel/eBPF visibility, or a
preinstalled privileged component, that is a new architecture decision under
ADR 0001's revisit triggers, not a change to this inventory.
