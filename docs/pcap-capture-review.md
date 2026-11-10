# Pcap capture and review extension

- **Status:** Implemented front-end contract, offline parser, preview wiring, and
  explicit non-root review helper
- **Date:** 2026-11-10
- **Scope:** The Capture review tab of the
  [Padilha security panel](security-panel.md)
- **Capture contract:** [`preview/security/pcap-capture.js`](../preview/security/pcap-capture.js)
- **Format contract:** [`preview/security/pcap-format.js`](../preview/security/pcap-format.js)
- **Offline helper:** [`tools/pcap_review_helper.py`](../tools/pcap_review_helper.py)
- **Policy:** [ADR 0001](adr/0001-grapheneos-base-device-support-and-padilha-branding.md) ·
  [privacy and security-tooling rules](legal/grapheneos-aosp-attribution.md#7-privacy-and-security-tooling-rules)

The extension adds user-started packet capture and completely offline capture
review to the security panel. It is an ordinary app surface plus an optional,
explicitly started **non-root helper** adapter. It is not a hidden capture
service, a privileged sniffer, a remote analysis service, or an upload path.
The capture contract id is `com.castela.pcap-capture`; the review contract id is
`com.castela.pcap-review`.

## 1. Capture consent and lifecycle

There is no capture on first launch. Construction of the contract performs no
work, starts no provider, opens no socket, reads no file, and starts no timer.
The initial state is `idle` with the persistent indicator hidden.

Live capture requires all of the following, in order:

1. The user authorizes lab mode with the ownership acknowledgement.
2. The user checks a separate capture-consent statement that names passwords,
   tokens, messages, and third-party personal data.
3. The user presses **Start capture**.
4. A local capture provider is present and passes validation.

Authorization alone does not start capture, and checking consent alone does not
start capture. A start request without authorization returns `not-authorized`;
a start request without the separate consent returns `consent-required`.

The future signed Castela app captures through a user-started Android
**VpnService** with a **persistent notification**. The provider contract uses
kind `android-vpn-service` for that path. An explicit user-installed non-root
helper can use kind `non-root-helper`; it must not require root or raw sockets.
Tests use kind `fixture` only. The preview itself never starts a live capture.

While capture is active the contract exposes:

- `state: "capturing"`;
- the capture id and a user-facing label;
- `indicator.visible: true` and `indicator.persistent: true`.

The panel renders that indicator outside the tab panel, so it stays visible
when the user switches tabs. **Stop capture** delegates to the provider's stop
function, hides the indicator, and keeps lab mode authorized. A provider that
cannot stop is rejected, because access could not be revoked cleanly.

Providers that declare privileges, root, raw sockets, hidden or automatic
capture, upload, or telemetry are rejected with `unsafe-provider`. A provider
without a persistent indicator is rejected with `indicator-required`.

The future app adapter has this shape; the preview does not include a real
VpnService implementation, so `start` and `stop` must be wired to the signed
app's foreground service and notification in a later build:

```js
globalThis.CASTELA_CAPTURE_PROVIDER = {
  kind: "android-vpn-service",
  label: "Castela VpnService capture",
  persistentIndicator: true,
  start: (context) => ({ id: "capture-1", label: "Wi-Fi lab capture" }),
  stop: (context) => ({ stopped: true }),
  clear: (context) => ({ cleared: true }),
};
```

The provider receives the authorized session id, the separate consent flag,
and `persistentNotification: true`. The app, not the preview, owns the actual
tunnel and notification lifecycle.

## 2. Offline pcap review

Review is local and read-only. The panel reads the file only after the user
presses **Review selected capture**; selecting a filename does not read its
contents. Supported formats are:

- classic **pcap**, microsecond and nanosecond timestamps, both byte orders;
- **pcapng**, both byte orders, with interface timestamp resolution.

The summary contains:

| Field | Contents |
| --- | --- |
| Format | pcap/pcapng, version, byte order, timestamp resolution, link type |
| Counters | Packet count, captured bytes, original bytes, truncated packets |
| Time range | First and last timestamp, duration |
| Protocols | IPv4, IPv6, ARP, TCP, UDP, ICMP, and undecoded packets |
| Endpoints | Top addresses with packet and byte counts |
| Conversations | Top protocol/address/port pairs with packet and byte counts |
| Ports | Top observed TCP/UDP ports |
| Payload | Payload packet and byte counts only, never payload contents |
| Sensitivity | Payload presence, plaintext-service hints, and risk level |
| Warnings | Sensitive payloads, plaintext services, truncation, parse errors |

Payload contents are never copied into the summary, the DOM, a log, or an
export. The parser extracts only addresses, ports, protocol numbers, counters,
and sizes. A fixture containing recognizable secret strings is used to prove
that those strings never appear in the serialized summary.

## 3. Sensitive payloads and no upload

Packet captures may contain passwords, tokens, cookies, private messages, and
third-party personal data. The panel warns about sensitive payloads and shows a
visible warning in the capture tab. It also returns explicit `sensitive-payload`
and `plaintext-service` warnings from the summary. The contract and preview
contain no `fetch`, `XMLHttpRequest`, `WebSocket`, beacon, worker, service
worker, or remote resource.

Captures are **never uploaded automatically**; there is no upload control and no
remote endpoint in this extension. Any future export or share action requires a
new review, a fresh warning, and a user-selected destination. Nothing is sent
off the device by this implementation.

## 4. Revoke access and clear captures

**Stop and clear** in the panel:

1. stops an active capture and hides the persistent indicator;
2. calls the provider's clear function to delete captured files;
3. removes the in-memory review, selected file reference, and session results;
4. revokes lab-mode authorization and drops the session.

After revocation, every start or review request returns `not-authorized` until
the user authorizes again. **Clear captures** is a separate explicit request.
It requires `confirmed: true`, refuses while a capture is still active, and
delegates deletion to the provider's clear function. Without a provider clear
function the result is `clear-unavailable`; the panel does not claim that files
were deleted when it cannot verify it. The panel never requests
`MANAGE_EXTERNAL_STORAGE`.

## 5. Offline non-root helper

The bundled helper reviews a capture the user already has. It does not capture
live traffic, open sockets, run subprocesses, need root, or upload anything:

```bash
python3 tools/pcap_review_helper.py --input capture.pcap --pretty
cat capture.pcapng | python3 tools/pcap_review_helper.py
```

It reads bytes from stdin or `--input`, summarizes only packet metadata, and
counts payload bytes without printing them. The app-side contract re-summarizes
the same bytes, so a helper cannot inject payload text into the display. The
helper is an explicit, user-started path for offline review; live capture on
Android still belongs in a user-started VpnService with a persistent
notification.

## 6. Tests and fixtures

The test suite generates a **generated pcap fixture** at test time, so no
capture file is committed. The fixture contains Ethernet, ARP, IPv4, TCP, UDP,
recognizable secret payload strings, and a truncated variant. A generated
pcapng fixture exercises the second format.

Covered cases include:

- classic pcap in both byte orders and both timestamp resolutions;
- pcapng section/interface/enhanced-packet parsing;
- packet counters, protocol counts, endpoints, conversations, ports, time range;
- malformed, empty, truncated, and packet-limited captures;
- secret payload strings never present in the serialized summary;
- no capture provider call on construction or authorization;
- start refusal without authorization or separate consent;
- persistent indicator visible only while capturing;
- stop, restart, revocation, and provider clear calls;
- unsafe providers, async providers, and throwing start/stop/clear paths;
- the Python helper's fixture summary, stdin/file modes, and refusal paths;
- no timers, network calls, workers, storage, or automatic actions in the
  contracts, and no remote URLs in the preview.

There is **no live capture** in CI. The tests need no device, network, root,
Termux, `tcpdump`, or Android SDK. Run the focused test and then the repository
suite:

```bash
python3 -m unittest tests.test_pcap_capture -v
bash tests/all.sh
```

## 7. Android build boundary

The preview is HTML/CSS/JavaScript because this repository does not contain a
Gradle project or Android SDK. A future signed APK must preserve the same
contract using **public Android APIs**:

- `VpnService` only for a user-started capture, with a foreground service, a
  persistent notification, and a stop action;
- Storage Access Framework for a user-selected capture file;
- app-private storage and a verified delete for captured files;
- no root, raw sockets, privileged permissions, `android:sharedUserId`,
  `QUERY_ALL_PACKAGES`, or `MANAGE_EXTERNAL_STORAGE`.

The app must not start capture at boot, in the background, or on first launch.
If a future requirement needs privileged packet access, kernel/eBPF visibility,
or a preinstalled capture service, that is a new architecture decision under
ADR 0001's revisit triggers, not a change to this extension.

## 8. Known limits

- This is a front-end contract, offline parser, and review helper, not a signed
  Android app and not a claim that a device has been instrumented.
- The preview cannot start a live capture without an injected provider; the
  stock preview therefore stays in a clearly labelled capture-unavailable state.
- The parser decodes common Ethernet, Linux cooked, null/loopback, raw IPv4, and
  raw IPv6 link types. Unknown link types are counted and reported, not guessed.
- The summary is metadata only. It is not an intrusion-detection system, a
  protocol dissector for every application layer, or a forensic chain-of-custody
  tool.
- GrapheneOS remains responsible for verified boot, OS updates, and system
  security. This extension does not change them.
