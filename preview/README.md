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

This directory is static and offline: no build step, no package manager, no
network calls, no telemetry. `palette-data.js` is generated from
`docs/branding/tokens.json`:

```bash
python3 tools/export_preview_tokens.py
```

Do not edit `palette-data.js` by hand.

The security panel's pure registration/state contract lives in
`security/security-panel.js`; `security/security.js` only binds it to the page.
There are no timers, workers, network calls, or automatic scans. Optional local
tool probes can be injected through `globalThis.CASTELA_SECURITY_TOOLS` during
development; without an adapter every tab shows a graceful missing-tool state.
