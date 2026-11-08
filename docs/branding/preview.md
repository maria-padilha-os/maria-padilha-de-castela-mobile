# Stock-device Padilha preview

- **Status:** Implemented
- **Date:** 2026-11-08
- **Scope:** [`overlay-and-build.md`](overlay-and-build.md)
- **Tokens:** [`tokens.json`](tokens.json)

The preview is a static, offline browser surface. It lets you inspect the
Padilha palette, wallpaper, fonts, icons, dynamic-accent fallback, and contrast
report **on stock GrapheneOS before touching a system partition**. It uses the
browser already on the device; it does not install an APK, request Android
permissions, or need root.

## 1. Run it

From this checkout:

```bash
python3 preview/serve.py --bind 127.0.0.1 --port 8099
```

The server is read-only and refuses common key, artifact, and build-output
paths. Leave it on loopback unless you understand that it has no authentication.

### Phone or emulator

1. Enable USB debugging and connect the device.
2. Forward the local port over `adb` (non-privileged, no root):

   ```bash
   adb reverse tcp:8099 tcp:8099
   ```

3. Open `http://127.0.0.1:8099/preview/` in the device browser.
4. Stop the forward when finished:

   ```bash
   adb reverse --remove tcp:8099
   ```

The same `adb reverse` path works for the GrapheneOS emulator. If you run the
browser and server on the same machine, open the URL directly.

### Install as a home-screen shortcut (optional)

The preview includes a web app manifest and local icons. Use the browser's
"Add to Home screen" action if it is offered. No service worker, background
process, network request, or telemetry is included.

## 2. What the preview covers

| Control | What it demonstrates |
| --- | --- |
| System / Light / Dark | The same palette resolver used by the tests; system mode follows `prefers-color-scheme` |
| Noite / Amanhecer | Dark and light wallpaper variants from `assets/wallpapers` |
| Dynamic accent | A candidate accent is accepted only if accent-on-background, accent-on-surface, accent-on-raised-surface, and text-on-accent all pass 4.5:1 |
| Contrast report | Live ratios for body text, secondary text, accent, status colours, and borders |
| Fallback message | Dynamic accent rejection, partial-token fallback, or missing-palette fallback |

The launcher mock puts clock, search, app labels, and dock content on Padilha
surface tokens instead of relying on the wallpaper. That is deliberate: a busy
wallpaper must not be able to make a label unreadable.

The preview does **not** show or change:

- the boot animation, system font, system UI, Settings, lock screen, notification
  shade, Quick Settings, or default apps;
- verified boot, AVB, app signing, the package installer, permissions, or the
  security panel's trusted UI;
- any file outside this checkout.

## 3. Offline and private by design

- No CDN, analytics, telemetry, remote font, or remote image.
- All icon, font, and wallpaper URLs are relative local paths.
- The preview never writes to the device or the checkout.
- The server binds to `127.0.0.1` by default.
- No Android permission, `VpnService`, root, or privileged command is used.

## 4. Test the preview and assets

```bash
bash tests/all.sh
```

The suite checks asset paths and dimensions, generated Android vectors, overlay
targets, missing-palette fallback, dynamic-accent rejection, contrast, and that
no CSS text colour is a hardcoded light literal on a light surface.

## 5. Known limits

- Browser rendering is not a pixel-exact substitute for a Compose or Views
  layout. Verify spacing, 200% text, TalkBack, and reduced motion in the real
  app once the launcher module is built.
- The preview has no real launcher data, widgets, work profile, or app drawer.
- It is a design-system preview, not a claim that the device boots with Castela
  branding. Stock GrapheneOS boot and system UI remain in place.
- A future system-image track still needs a new ADR, signing ceremony, and boot
  validation. Nothing here authorizes that track.
