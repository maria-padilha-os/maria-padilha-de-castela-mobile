# Overlay, asset, and system-build boundaries

- **Status:** Implemented design assets, resources, preview, and tests
- **Date:** 2026-11-08
- **Decision record:** [ADR 0001](../adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- **Tokens:** [`tokens.json`](tokens.json)
- **Preview:** [`preview.md`](preview.md)
- **Asset provenance:** [`asset-provenance.md`](asset-provenance.md)
- **Security policy:** [GrapheneOS, AOSP, and redistribution rules](../legal/grapheneos-aosp-attribution.md)

This document records exactly how the Padilha design system is applied to
Castela Mobile and which parts stay out of the stock-device path. The short rule
is: **the app layer is themeable, the system image is not.**

## 1. Surface matrix

| Surface | Mechanism in this repository | Installable on stock GrapheneOS | System build required |
| --- | --- | --- | --- |
| Palette in Castela apps | `android/design` colour resources, light and `values-night` dark | Yes, as part of the app | No |
| Palette in a Castela-owned app | Optional signed runtime resource overlay in `android/overlays/padilha-palette` | Yes, only as an explicitly enabled overlay for that app | No |
| Launcher wallpaper | `assets/wallpapers` WebP/PNG; set by user action through `WallpaperManager` | Yes, in the launcher/theme app | No |
| App and launcher fonts | Bundled Fraunces and Inter, `assets/fonts` and `android/design/src/main/res/font` | Yes, inside Castela apps only | No |
| Launcher icons and icon pack | Original 24 dp icons, adaptive/monochrome layers in `assets/icons` and `assets/android-res` | Yes, as launcher assets | No |
| Boot animation | Source keyframes and `desc.txt` in `android/system/bootanimation` | **No** | **Yes** |
| System font | Not changed | No | Yes |
| System UI, Settings, notification shade, Quick Settings | Not changed | No | Yes |
| Lock screen / Always On Display | Only the user-chosen wallpaper may appear | Wallpaper only | For system-level styling |
| Default apps | Not preinstalled | User chooses | Yes |
| Verified boot, AVB, OS signing, update trust root | **Untouched** | Not applicable | Forbidden without a new ADR and signing ceremony |

The stock GrapheneOS boot sequence remains visible. Castela does not root the
device, remount `/system`, replace `/system/media/bootanimation.zip`, or ship a
fake full-screen boot video inside an app. The stock boot animation therefore
stays in place until a separately authorized system-image build replaces it.

## 2. Runtime resource overlays

`android/overlays/padilha-palette` is a reference **runtime** resource overlay
(RRO), not a static system overlay:

- It targets one Castela-owned package, currently the placeholder
  `com.castela.mobile`. Build one overlay per Castela package if needed.
- It must never target `android`, `com.android.systemui`, `com.android.settings`,
  `com.android.packageinstaller`, or any other security-critical component.
- It overrides **colour tokens only**. Layouts, security UI, permissions,
  exported components, and signing configuration are not overlayable.
- The base app declares the allowed colour names in
  `android/design/src/main/res/values/overlayable.xml`.
- The overlay has `android:hasCode="false"` and no permissions.
- It is not part of the stock-device preview. Enabling an RRO is a development or
  signed-app-suite action; it does not write to a system partition.

A privileged static overlay in the system image is a different artifact and is
not authorized by ADR 0001. If a future system image is approved, it still must
not let a theme overlay reach verified boot, the package installer, permission
controllers, the lock screen, or the security panel's trusted UI.

## 3. Dynamic light/dark palette

The fixed Padilha palette is the default. Dynamic colour is an optional accent
tint, not a replacement for the semantic system:

1. Resolve the system theme to Padilha `light` or `dark` (or the user's manual
   override inside Castela apps).
2. If a dynamic accent is offered, test it against the active background,
   surface, and raised surface at **4.5:1**.
3. Choose `onAccent` as black or white, whichever has more contrast, and require
   **4.5:1** for text on the accent.
4. If any check fails, keep the canonical Padilha accent. Report the failure; do
   not force the tint.
5. If the token file is missing, unreadable, malformed, or partial, fill every
   missing or invalid token from the built-in Padilha fallback. Never leave light
   text on a light surface.

The executable contract is [`design/padilha_palette.py`](../../design/padilha_palette.py).
The browser preview reimplements the same rule in `preview/palette.js`. The
Android resource layers are:

- `android/design/src/main/res/values/colors.xml`: light fallback and default.
- `android/design/src/main/res/values-night/colors.xml`: dark.
- `android/design/src/main/res/values/overlayable.xml`: the only overlayable
  colour names.
- `android/overlays/padilha-palette/res/values{,-night}`: optional RRO copy.

Dynamic colour may tint `accent` and `onAccent` only. Text, surfaces, borders,
and semantic success/warning/danger colours stay fixed so a platform palette
cannot silently destroy the security panel's legibility or status semantics.

## 4. Asset map

| Asset | Canonical path | Output |
| --- | --- | --- |
| Dark wallpaper master | `assets/wallpapers/source/padilha-dark.svg` | `assets/wallpapers/masters/padilha-dark-1440x3120.png`, `assets/wallpapers/padilha-dark-1440x3120.webp` |
| Light wallpaper master | `assets/wallpapers/source/padilha-light.svg` | `assets/wallpapers/masters/padilha-light-1440x3120.png`, light WebP |
| Compact phone crops | rendered from the masters | `assets/wallpapers/padilha-{dark,light}-1080x2424.webp` |
| Tablet/foldable crops | best effort from the masters | `assets/wallpapers/padilha-{dark,light}-{2560x1600,1600x2560}.webp` |
| Fraunces | `assets/fonts/Fraunces-Variable.woff2`, `assets/android-res/font/fraunces_variable.ttf` | OFL text in `assets/fonts/OFL-Fraunces.txt` |
| Inter | `assets/fonts/Inter-{Regular,Medium,SemiBold}.woff2`, `assets/android-res/font/inter_variable.ttf` | OFL text in `assets/fonts/OFL-Inter.txt` |
| Icons | `assets/icons/*.svg` (24 dp, 2 dp stroke) | Android vectors in `assets/android-res/drawable/*.xml` |
| Adaptive icon | `assets/android-res/drawable/ic_launcher_foreground.xml` | `mipmap-anydpi-v26` and `-v33` launcher XML with a monochrome layer |
| Boot source | `assets/bootanimation/source/padilha-boot-*.svg` | System-build `part0/` frames; never a tracked ZIP |

The wallpaper art is original abstract linework. It contains no text, deity,
altar, possession scene, living-person likeness, or GrapheneOS/Android/Google/
Pixel mark. The launcher, not the wallpaper, is responsible for label contrast:
the preview puts labels on the `scrim`/`onScrim` token pair instead of relying on
the artwork. Both themes pair them above 15:1.

## 5. Build integration

The source is intentionally not a full Gradle project in this task; there is no
Android SDK in the repository and no ROM is built or flashed. Build integration
is expected to:

- include `android/design/src/main/res` and `assets/android-res` as resource
  sources for the Castela design/launcher modules;
- build `android/overlays/padilha-palette` as a separate signed APK if that
  optional overlay is used, one target package per overlay;
- keep `assets/fonts/OFL-*.txt` with the bundled font outputs;
- run `tests/all.sh` before release;
- generate `bootanimation.zip` only inside a future, separately authorized
  system-image build. The ZIP stays out of Git and out of the app layer.

This task does **not** change verified boot, AVB keys, app signing keys, the OS
update channel, the package installer, permission controllers, or any
security-critical UI.

## 6. Security invariants

- No root, `sudo`, `pkexec`, `systemctl`, `pacman`, `mount`, or system-partition
  write is part of the build, preview, or tests.
- No `android:sharedUserId`, hidden API, privileged permission, or exported
  system component is introduced.
- No theme asset is allowed to change a security decision, an authentication
  surface, a permission prompt, or a status indicator's meaning.
- Status colours are always paired with an icon and a text label.
- The preview is read-only and offline. It makes no network calls and requests no
  Android permissions.
- The repository and its artifacts remain private.
