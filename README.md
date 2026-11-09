# Castela Mobile

Private cybersecurity mobile experience for GrapheneOS, with the look and feel
of Maria Padilha. **This repository and all build artifacts must remain
private.**

This is **not official GrapheneOS**. It is an independent project that runs on
official GrapheneOS and adds a Padilha app layer: a launcher, wallpaper and
theme assets, a local security panel, and a setup companion. It is not a
GrapheneOS fork, an official GrapheneOS build, or an "unofficial build" of
GrapheneOS.

## Status

**Architecture decision accepted.** [ADR 0001](docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
selects a device-side Padilha overlay plus companion apps on top of official
GrapheneOS, rather than a full GrapheneOS fork and system-image build.

- Reference device: **Pixel 9a (`tegu`)**, supported by GrapheneOS through
  April 2032.
- First milestone: a private app suite, not a system image.
- The Padilha design layer is implemented as Android resources, launcher assets,
  and an offline stock-device preview. No ROM has been built. No device has been
  flashed. No artifact has been released.

A full fork is deferred and requires a new ADR. See the
[revisit triggers](docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md#revisit-triggers).

## Decision summary

- GrapheneOS remains the operating system and the source of OS, firmware,
  kernel, and browser/WebView security updates.
- Castela ships only its own signed apps: the Padilha launcher, theme/icon/
  wallpaper layer, security panel, and setup companion.
- The app layer covers wallpaper, palette, fonts inside Castela apps, icons, and
  the launcher. It does **not** change the boot animation, system font, system
  UI, or preinstalled defaults; those require a system image and are out of
  scope.
- The repository and artifacts stay private. Distribution to testers is a
  redistribution event and requires the legal checklist.
- The product is presented as "Castela Mobile, an independent project that runs
  on GrapheneOS." Do not use the GrapheneOS name or logo as product branding.

## Padilha design-system implementation

The app-layer design system now has concrete sources under `android/`, `assets/`,
and `preview/`:

- light and `values-night` colour resources, plus an optional runtime resource
  overlay scoped to a Castela-owned package only;
- original dark/light wallpapers, Fraunces and Inter font families, original
  icons, adaptive/monochrome launcher layers, and a system-build-only boot
  animation source;
- a dynamic-accent resolver that rejects failing colours and falls back to the
  fixed Padilha palette when tokens are missing or partial;
- an offline browser preview that runs on stock GrapheneOS before any system
  partition is touched;
- a dedicated security-panel front-end with authorized lab mode, explicit
  stop/clear, four inspection tabs, and graceful missing-tool states;
- a local-network inventory extension with private/link-local range validation,
  explicit ownership confirmation, provider-based discovery, and fixture-tested
  host/address/service-hint display.

The boot animation, system font, system UI, lock screen, and default-app
preinstallation still require a system image and a new ADR. Verified boot,
signing, and security-critical UI are unchanged. See
[overlay and build boundaries](docs/branding/overlay-and-build.md) and the
[stock-device preview](docs/branding/preview.md).

## Documentation

- [ADR 0001: GrapheneOS base, device support, and Padilha branding](docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- [Attribution, trademark, and redistribution rules](docs/legal/grapheneos-aosp-attribution.md)
- [Padilha look-and-feel scope](docs/branding/padilha-look-and-feel.md)
- [Overlay and system-build boundaries](docs/branding/overlay-and-build.md)
- [Stock-device preview](docs/branding/preview.md)
- [Security panel contract and safety boundaries](docs/security-panel.md)
- [Local-network inventory contract, ranges, and helper](docs/local-network-inventory.md)
- [Asset provenance](docs/branding/asset-provenance.md)
- [Machine-readable design tokens](docs/branding/tokens.json)

## Planned surface

- Padilha launcher with app drawer, local search, folders, widgets, work-profile
  support, and accessible light/dark themes
- original wallpaper, palette, icon pack, and typography inside Castela apps
- a dedicated local security panel with authorized lab mode (front-end
  implemented in `preview/security/`; the signed app remains a build task)
- local network inventory with private/link-local range validation and an
  explicit Termux/native helper (front-end contract implemented; pcap review and
  permission/integrity audits remain planned)
- no automatic scanning, no hidden privileged service, no root, no telemetry
- a setup companion that checks compatibility and links to the official
  GrapheneOS installation and update documentation

Out of scope for this phase: installing or replacing the boot animation, system
font replacement, system UI theming, preinstalled default apps, bootloader
unlocking, ROM builds, and device flashing. The boot animation source in this
repository is for a future system-image track only.

## Safety and privacy

Do not flash a device until the device matrix, recovery documentation, and
signed build pipeline exist. Do not publish builds or artifacts; the repository
and release artifacts remain private. Do not claim this is official GrapheneOS.

The security panel is an ordinary app. It does not provide kernel, baseband, or
privileged visibility, and it must not claim to. Packet captures may contain
personal data: capture only on networks you own or are authorized to test, keep
data local, and delete it when finished. The local-network inventory accepts
only private/link-local ranges, requires an explicit ownership confirmation
before any provider runs, and never probes ports, exploits services, or captures
credentials.

## License

Original Castela code and documentation are GPL-3.0-only per repository policy.
Third-party components and assets retain their own licenses; see the
[legal rules](docs/legal/grapheneos-aosp-attribution.md). A top-level `LICENSE`
file is a release follow-up.

## Relationship to the other repositories

The Padilha design language and shell work live in
[`maria-padilha-de`](https://github.com/maria-padilha-os/maria-padilha-de).
The normal mobile OS is
[`maria-padilha-mobile`](https://github.com/maria-padilha-os/maria-padilha-mobile).
The desktop cyber image is
[`maria-padilha-de-castela`](https://github.com/maria-padilha-os/maria-padilha-de-castela).
