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

This directory is static and offline: no build step, no package manager, no
network calls, no telemetry. `palette-data.js` is generated from
`docs/branding/tokens.json`:

```bash
python3 tools/export_preview_tokens.py
```

Do not edit `palette-data.js` by hand.
