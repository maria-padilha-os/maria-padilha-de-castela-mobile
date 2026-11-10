# Padilha stock-device preview

Read [`docs/branding/preview.md`](../docs/branding/preview.md) first. Quick start:

```bash
python3 preview/serve.py --bind 127.0.0.1 --port 8099
# then open http://127.0.0.1:8099/preview/
```

On a USB-connected phone or emulator:

```bash
adb reverse tcp:8099 tcp:8099
```

Open the same URL in the device browser. Stop the forward afterward with
`adb reverse --remove tcp:8099`.

The dedicated security panel is at `http://127.0.0.1:8099/preview/security/`.
It is a separate surface from the launcher and general settings: lab mode starts
locked, every action is user-initiated, and missing local tools render as
explicit unavailable states. See [`docs/security-panel.md`](../docs/security-panel.md).

The **Network inventory** tab uses the
[local-network inventory contract](../docs/local-network-inventory.md). It
accepts only validated private/link-local ranges and requires the ownership
acknowledgement before a provider runs. A provider is injected through
`globalThis.CASTELA_NETWORK_PROVIDER`; without one the tab stays in a
missing-provider state. The explicit
[Termux/native helper](../tools/network_inventory_helper.py) can read a neighbor
cache that the user supplies. Tests use fixture data only and never scan a live
network.

The **Capture review** tab uses the
[pcap capture/review contract](../docs/pcap-capture-review.md). Offline review
is built in and reads a user-selected pcap or pcapng file only when the user
presses the review action. It summarizes packet metadata, never keeps or shows
payload contents, and warns about sensitive payloads. Live capture requires an
explicit provider injected through `globalThis.CASTELA_CAPTURE_PROVIDER`; the
stock preview never starts one. A user-started Android `VpnService` or an
explicit non-root helper provider must keep a persistent indicator and a stop
control. Tests generate pcap fixtures and never capture live traffic.

This directory is static and offline: no build step, no package manager, no
network calls, no telemetry. `palette-data.js` is generated from
`docs/branding/tokens.json`:

```bash
python3 tools/export_preview_tokens.py
```

Do not edit `palette-data.js` by hand.

The security panel's pure registration/state contract lives in
`security/security-panel.js`; the inventory contract lives in
`security/network-inventory.js`; the capture/review contracts live in
`security/pcap-capture.js` and `security/pcap-format.js`. `security/security.js`
only binds them to the page. There are no timers, workers, network calls, or
automatic scans. Optional local tool probes can be injected through
`globalThis.CASTELA_SECURITY_TOOLS`, an explicit inventory provider through
`globalThis.CASTELA_NETWORK_PROVIDER`, and an explicit live-capture provider
through `globalThis.CASTELA_CAPTURE_PROVIDER` during development. Without
adapters the network and live-capture paths show graceful missing-provider
states; offline pcap review remains available.
