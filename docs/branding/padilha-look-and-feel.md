# Padilha look-and-feel scope

- **Status:** Design scope for the app-layer approach
- **Date:** 2026-11-06
- **Decision record:** [ADR 0001](../adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- **Tokens:** [`tokens.json`](tokens.json)
- **Legal rules:** [Attribution, trademark, and redistribution](../legal/grapheneos-aosp-attribution.md)

This document defines what "Padilha look and feel" means for Castela Mobile. It
is intentionally a scope, not a finished visual identity: it fixes the surfaces,
tokens, legibility requirements, and asset rules so implementation does not
invent them ad hoc.

The chosen architecture is an app-layer overlay on official GrapheneOS. That
means some surfaces are in scope and some are not. The out-of-scope list is as
important as the in-scope list.

## 1. Design principles

1. **Legible before decorative.** A beautiful surface that fails contrast, touch
   targets, or screen-reader order is a defect.
2. **Night, lace, and candlelight — not costume.** The palette and motifs should
   feel editorial and grounded, not like a party or a religious parody.
3. **Original and respectful.** Maria Padilha is a cultural and religious figure.
   Use original art and consult people from the relevant communities when a
   symbol is more than decorative.
4. **Quiet confidence.** Prefer one strong focal element, generous spacing, and
   restrained gold accents over visual noise.
5. **No false signals.** Do not use GrapheneOS, Android, Google, or Pixel marks.
   Do not make the app look like a system component it is not.
6. **Accessible by default.** Light and dark themes, 200% text, reduced motion,
   TalkBack, and color-vision checks are acceptance criteria, not follow-ups.

## 2. Surface scope

| Surface | In scope for Option B (stock GrapheneOS + apps) | Notes |
| --- | --- | --- |
| Wallpaper | Yes | Original art; dark and light variants; phone and best-effort tablet/foldable crops |
| Palette | Yes | Fixed tokens in Castela apps and launcher; optional dynamic-color mode only if it passes contrast |
| Fonts | Yes, inside Castela apps and launcher | Fraunces + Inter; system font is **not** changed |
| Icons | Yes, launcher and Castela apps | Adaptive, monochrome, and legacy fallbacks; third-party logos stay recognizable |
| Launcher | Yes | User-installed default-home replacement |
| Boot animation | **No** | Stock GrapheneOS animation remains; no root or `/system` modification |
| System UI / Settings | **No** | Cannot theme without a system image |
| Default apps | **No** | User installs and chooses defaults |
| OS OTA / update screens | **No** | GrapheneOS owns OS updates; Castela has its own app-update screen |
| Lock screen / Always On Display | **No, except wallpaper-derived background** | No system-level lock-screen customization |
| Notification shade / Quick Settings | **No** | No system UI theming in Option B |

A future system-image track (Option A) may bring boot animation, system font, and
system UI into scope. That requires a new ADR, new signing keys, and a new
security review. It is not authorized by this document.

## 3. Wallpaper

### Art direction

The working direction is **"Noite de Padilha"**: a deep plum/indigo night with
warm candle-gold highlights, abstract lace or embroidery linework, and a subtle
wine/rose accent. The image should be atmospheric and abstract. It must not
depict a deity, altar, possession scene, or a specific living person.

### Deliverables

| Variant | Size | Format | Notes |
| --- | --- | --- | --- |
| Phone dark master | 1440 × 3120 | PNG master, WebP q90 delivery | sRGB; retain master privately |
| Phone light master | 1440 × 3120 | PNG master, WebP q90 delivery | Same composition, lighter values |
| Phone compact | 1080 × 2424 | WebP q90 | Pixel 9a crop of the master; do not upscale |
| Tablet/foldable | 2560 × 1600 and 1600 × 2560 | WebP q90 | Best-effort; test open/closed and landscape |
| Optional monochrome | 1440 × 3120 | PNG/WebP | For OLED/reader modes; must remain recognizable |

Runtime targets: each delivered wallpaper should be under 2.5 MiB where
possible. Keep the lossless master out of the app bundle and in the private
design archive.

### Composition and safe zones

- Keep the primary focal point in the upper-middle third, not directly behind
  the app grid or the dock.
- Top 10%: status bar and camera cutout. Bottom 20%: dock and gesture area.
  Keep these areas low-frequency and low-contrast.
- No text, QR codes, logos, or UI mockups in the wallpaper.
- Test with light and dark icon labels, a 20–40% scrim, and a blur. If an icon
  label is unreadable, the wallpaper is too busy in that zone.
- Provide a scrim token/overlay so the launcher can guarantee label contrast
  rather than relying on the artwork.

### Wallpaper picker behavior

- Offer dark and light variants explicitly; do not infer only from system theme.
- Preview both the home screen and lock screen crop.
- Setting a wallpaper is a user action. No automatic rotation, no network
  download, no bundled third-party wallpaper.
- Respect per-user profiles; do not copy one profile's wallpaper into another.

## 4. Palette

`tokens.json` is the machine-readable source of truth. The values below are the
current implementation targets.

### Dark theme

| Token | Hex | Usage |
| --- | --- | --- |
| `background` | `#120C17` | App and launcher background; not pure black |
| `surface` | `#1D1424` | Cards, sheets, grouped rows |
| `surfaceRaised` | `#2A1D33` | Menus, dialogs, elevated controls |
| `textPrimary` | `#F6EDE3` | Body and headings |
| `textSecondary` | `#CDBFCB` | Supporting text, metadata |
| `accent` | `#E58AA0` | Primary action, selected state, focus |
| `accentStrong` | `#E6B85C` | Gold highlight, progress, key numeric emphasis |
| `onAccent` | `#241A28` | Text/icons on `accent` |
| `onAccentStrong` | `#241A28` | Text/icons on `accentStrong` |
| `border` | `#8C7594` | Control boundaries and separators that convey structure |
| `success` | `#7CC49A` | Success status, always with icon/text |
| `warning` | `#E8B45A` | Warning status, always with icon/text |
| `danger` | `#F08A8A` | Destructive action/error, always with icon/text |

### Light theme

| Token | Hex | Usage |
| --- | --- | --- |
| `background` | `#FBF5EC` | Warm cream background |
| `surface` | `#F3E8DA` | Cards, sheets, grouped rows |
| `surfaceRaised` | `#FFFFFF` | Menus, dialogs, elevated controls |
| `textPrimary` | `#241A28` | Body and headings |
| `textSecondary` | `#5A4A57` | Supporting text, metadata |
| `accent` | `#7A2340` | Primary action, selected state, focus |
| `accentStrong` | `#7A5A1E` | Gold-brown highlight; not the bright gold on cream |
| `onAccent` | `#FFFFFF` | Text/icons on `accent` |
| `onAccentStrong` | `#FFFFFF` | Text/icons on `accentStrong` |
| `border` | `#7A6355` | Control boundaries and separators that convey structure |
| `success` | `#2F6B4A` | Success status, always with icon/text |
| `warning` | `#7A4E00` | Warning status, always with icon/text |
| `danger` | `#9B1C1C` | Destructive action/error, always with icon/text |

### Contrast targets

The table is a sample; `tests/check_contrast.py` checks every pair in
`tokens.json`.

| Pair | Dark | Light | Minimum |
| --- | --- | --- | --- |
| Body text on background | 16.63:1 | 15.46:1 | 4.5:1 |
| Body text on surface | 15.40:1 | 13.85:1 | 4.5:1 |
| Secondary text on background | 10.92:1 | 7.59:1 | 4.5:1 |
| Accent on background | 7.77:1 | 9.04:1 | 4.5:1 |
| Text on accent | 6.76:1 | 9.80:1 | 4.5:1 |
| Success on background | 9.37:1 | 5.83:1 | 4.5:1 |
| Warning on background | 10.18:1 | 6.64:1 | 4.5:1 |
| Danger on background | 7.98:1 | 7.52:1 | 4.5:1 |
| Border on background | 4.66:1 | 5.18:1 | 3.0:1 |

### Colour rules

- Accent colour is not a status colour. Do not use rose for "error" or gold for
  "success".
- Status is never conveyed by colour alone. Pair every semantic colour with an
  icon and a text label.
- Do not use pure black (`#000000`) as the dark background; the near-black plum
  avoids OLED smearing and keeps elevation readable.
- Do not use the bright gold `#E6B85C` as text on cream; use `accentStrong`
  `#7A5A1E` in the light theme.
- Dynamic colour (Material You) is optional. If enabled, it may tint the accent,
  but semantic colours, borders, and text must still be checked against the
  actual background. The fixed Padilha palette is the default.
- Disabled text is exempt from the 4.5:1 body requirement, but must still be
  distinguishable and must not carry essential information.

## 5. Typography

| Role | Family | Weights | Usage |
| --- | --- | --- | --- |
| Display | **Fraunces** (OFL 1.1) | 400–700 | Headings, launcher clock, large numerals, section titles |
| UI/body | **Inter** (OFL 1.1) | 400, 500, 600 | Body, controls, lists, security tables, dialog text |
| Fallback | System sans-serif | — | Used only when the bundled font cannot render a glyph |

Rules:

- Body text is at least **16 sp**; secondary text is at least **14 sp**.
- Line height is approximately **1.45** for body text. Avoid cramped leading in
  the security panel's data tables.
- Use weights below 400 only for large decorative display text, never for body
  or controls.
- Use tabular numerals for timestamps, byte counts, packet counts, and hashes.
- Avoid long all-caps strings. Short labels may use caps with tracking; body
  text must not.
- Limit body line length to roughly 60–75 characters on tablets and foldables.
- Test at 200% font scale with no clipped labels, overlapping controls, or
  truncated essential values.
- The system font is not replaced in Option B. Bundled fonts are used by Castela
  apps and the launcher only.
- Ship the OFL license text with the fonts. Do not rename a reserved font name
  without following the OFL's modification rules.

## 6. Icons

- **Grid:** 24 dp, 2 dp stroke, rounded caps and joins; optical alignment over
  mathematical centering.
- **Touch target:** at least 48 × 48 dp, even when the glyph is smaller.
- **Adaptive icons:** 108 × 108 dp with the foreground kept inside the 66 dp
  safe zone; provide a monochrome layer for themed icons.
- **Style:** rounded, slightly organic linework that echoes lace/embroidery
  without becoming ornate at 24 dp. Filled variants are for active/selected
  states; outlined variants are for idle states.
- **Third-party apps:** use the app's own icon by default. If a monochrome or
  themed icon is unavailable, use a tinted background/foreground fallback rather
  than redrawing the brand mark. Do not imply affiliation by altering a
  third-party logo.
- **System apps:** use original or Material Symbols icons. Material Symbols are
  Apache-2.0; keep the notice.
- **No logos:** do not use the GrapheneOS, Android, Google Play, or Pixel logos as
  icons or decorative marks.
- **Icon pack:** optional and user-selectable. The launcher must remain usable
  with the icon pack disabled. Do not require a third-party launcher or a
  proprietary icon-pack format.

## 7. Launcher

### Functional scope

- Default-home replacement with an app drawer, folders, dock, widgets, and
  notification dots.
- Local app search only by default. If contact/calendar search is added later, it
  must be opt-in and documented.
- Work-profile support with a clear badge and no cross-profile data leakage.
- TalkBack labels, focus order, and switch-access compatibility.
- Backup/restore of layout settings, excluding sensitive security-panel data.
- No internet permission by default; no telemetry; no automatic wallpaper or
  icon downloads.

### Visual scope

- Responsive grid: 4 columns on compact phones, 5 on larger phones, 6 on
  expanded/foldable/tablet widths; 16 dp outer margins.
- Icon labels: one line, ellipsized, 12 sp minimum; the full app name is available
  to TalkBack.
- Dock: 4–5 slots; the dock background is a subtle scrim, not a solid bar.
- Wallpaper legibility: apply a scrim or label shadow when the wallpaper's local
  luminance would fail contrast. The launcher, not the wallpaper, is responsible
  for label contrast.
- Light/dark: follow the system by default, with a manual override in launcher
  settings. The override must not affect other apps.
- Motion: page transitions 200–300 ms; no parallax by default; respect the
  system animation scale and reduced-motion setting.
- Performance target on the Pixel 9a: cold start under 500 ms, no visible jank
  on page swipes, and a resident memory budget that leaves room for the security
  panel on an 8 GiB device.

### Android integration

- Use `LauncherApps` rather than `QUERY_ALL_PACKAGES`.
- Use `AppWidgetHost` for widgets and follow the platform's widget resize rules.
- Do not use hidden APIs, reflection into system services, or a privileged
  `sharedUserId`.
- The user must explicitly select Castela as the default home app. Do not
  repeatedly prompt or block the system's home selection.
- Predictive back, gesture navigation, and the system's accessibility shortcuts
  must work.

## 8. Boot animation

### Option B (current decision)

The boot animation is **out of scope**. Official GrapheneOS keeps its own boot
animation. Castela must not:

- instruct users to root the device or remount `/system`;
- replace `/system/media/bootanimation.zip`;
- ship a fake full-screen "boot" video inside an app;
- claim that the device boots with Castela branding.

The brand moment moves to a **first-run setup transition** in `Padilha Setup`:
a short, static or subtly animated splash (no flashing, no autoplay audio) that
appears after the user opens the app, not during boot. The stock GrapheneOS boot
sequence remains visible and is described honestly in the documentation.

### Option A (future, only with a system-image ADR)

If a future system-image track is approved, the boot animation must meet these
requirements:

- 1080 × 2400 and 1440 × 3120 variants; 30 fps; 3–5 seconds; no audio.
- Dark plum background; subtle gold/lace line growth; no GrapheneOS, Android,
  Google, or Pixel marks; no text.
- No flashing above 3 Hz; no rapid luminance changes; provide a reduced-motion
  variant.
- `bootanimation.zip` with documented `part0`/`part1` loops; compressed only as
  the platform requires.
- Tested on a locked reference device for boot timing, fallback behavior, and
  recovery; signed into the system image as part of the release process.
- Accompanied by an updated legal review and signing-key ceremony.

## 9. Light/dark legibility and accessibility

### Requirements

- **WCAG 2.2 AA:** 4.5:1 for normal text, 3:1 for large text (≥ 18 pt regular or
  ≥ 14 pt bold), icons, focus indicators, and meaningful UI boundaries.
- **Target AAA where practical:** body text aims for 7:1, which the current
  palette exceeds.
- **Touch targets:** at least 48 × 48 dp with at least 8 dp spacing between
  adjacent targets.
- **Text scaling:** 200% without loss of content or function; no horizontal
  scrolling for body text except data tables, which must offer a readable
  alternative.
- **Screen readers:** meaningful labels, headings, and traversal order; decorative
  art is not announced; charts/tables have text summaries.
- **No color-only status:** success/warning/danger always have an icon and text.
- **Focus:** visible focus ring with at least 3:1 contrast against adjacent
  colours; do not rely on a subtle glow.
- **Motion:** respect `ANIMATOR_DURATION_SCALE`; offer a reduced-motion mode; no
  flashing above 3 Hz.
- **Sound:** no autoplay sound; any sound is user-initiated and can be disabled.

### Test matrix

| Test | Pass criterion |
| --- | --- |
| Light theme, body text | ≥ 4.5:1 on every surface |
| Dark theme, body text | ≥ 4.5:1 on every surface |
| Large text/icons/borders | ≥ 3:1 |
| 200% font scale | No clipped labels, overlapping controls, or lost function |
| TalkBack | Every control reachable and named; decorative art skipped |
| Grayscale | Status and selection still understandable without hue |
| Deuteranopia/protanopia/tritanopia simulation | No meaning lost; semantic icons/text remain |
| Sunlight/low brightness | Text remains readable; no pure-white flash surfaces |
| Reduced motion | No parallax, no autoplay animation, no flashing |
| Foldable/tablet | Layout adapts; no stretched phone UI |
| Security panel data table | Tabular numerals, readable at 200%, text summary available |

## 10. Motion and sound

- Standard transitions: 200–300 ms; large surface transitions: up to 400 ms.
- Easing: decelerate for entering, accelerate for exiting; avoid bounce for
  security actions.
- No autoplay video, no parallax by default, no confetti, no flashing.
- Haptics are optional and must respect system settings.
- Sound is off by default for the security panel; a capture start/stop chirp is
  allowed only if the user enables it.

## 11. Asset licensing and provenance

Every asset must have a record with:

- file name and version;
- author/artist;
- source (original, commissioned, or licensed);
- license (project GPL-3.0-only, OFL-1.1, Apache-2.0, etc.);
- date and modifications;
- reviewer for culturally sensitive motifs.

Rules:

- Original wallpaper and icon artwork is preferred. Do not scrape images from
  the web, social media, or AI generators without a rights review.
- Fonts must be OFL/Apache-2.0 compatible; ship their license texts.
- Icons from Material Symbols are Apache-2.0; keep the notice.
- Do not use the GrapheneOS, Android, Google Play, or Pixel logos.
- Do not use a real person's likeness without consent and a publicity-rights
  review.
- Keep the lossless masters and provenance records private; ship only derived
  assets.

## 12. Acceptance checklist

- [ ] `tokens.json` passes `tests/check_contrast.py`.
- [ ] Dark and light wallpapers exist at the required sizes, with no text or
      third-party marks.
- [ ] Fraunces and Inter are bundled with their OFL texts; system font is
      unchanged.
- [ ] Icons use the 24 dp/2 dp system, adaptive/monochrome layers, and 48 dp
      touch targets.
- [ ] Launcher installs on the Pixel 9a, can be set as default home, and passes
      app drawer, search, folder, widget, work-profile, and TalkBack smoke tests.
- [ ] Light/dark screenshots pass the contrast and 200% text checks.
- [ ] Boot animation is unchanged; docs and UI say so.
- [ ] No GrapheneOS, Android, Google Play, or Pixel logo appears in any asset.
- [ ] The "independent project, not official GrapheneOS" disclaimer appears in
      the README, About screen, and release notes.
- [ ] The security panel never claims kernel, baseband, or privileged visibility
      it does not have.

## 13. Open questions

1. Who is the commissioned artist for the wallpaper and icon suite, and what is
   the provenance/license record?
2. Should dynamic colour be offered at all, or only the fixed Padilha palette?
3. Which icon-pack format should the launcher expose, if any?
4. Is search limited to apps, or should it optionally include contacts/calendar
   with separate consent?
5. What are the Portuguese/English copy and localization rules for the launcher
   and security panel?
6. Which foldable/tablet layouts are actually supported versus best-effort?
7. Should the security panel be a separate app or a launcher surface with a
   separate package?

## 14. References

- [ADR 0001](../adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- [Attribution, trademark, and redistribution rules](../legal/grapheneos-aosp-attribution.md)
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [Material Symbols](https://fonts.google.com/icons?icon.set=Material+Symbols)
- [Fraunces](https://fonts.google.com/specimen/Fraunces)
- [Inter](https://rsms.me/inter/)
- [SIL Open Font License 1.1](https://openfontlicense.org/)
