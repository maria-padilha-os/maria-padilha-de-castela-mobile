# Castela Mobile

[![❤ Sponsor on GitHub](https://img.shields.io/badge/%E2%9D%A4%20Sponsor-GitHub-ea4aaa?logo=githubsponsors&logoColor=white)](https://github.com/sponsors/Mateus-M-Reis)

Privacy-focused cybersecurity mobile experience for GrapheneOS, with the look
and feel of Maria Padilha. **The source is public; build and release artifacts
remain private.**

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
- The [device support and flashing runbook](docs/device-support-and-flashing.md)
  documents the supported path onto a physical Pixel: official GrapheneOS, a
  manual bootloader unlock/flash/lock, then signed Castela apps. The repository
  never flashes a device.
- The Padilha design layer is implemented as Android resources, launcher assets,
  and an offline stock-device preview. No ROM has been built. No device has been
  flashed. No artifact has been released.
- A private release and signing pipeline is implemented for app, OTA, and
  factory-image artifacts. Keys live outside the repository, a checksum manifest
  covers every signed file, and signing requires explicit named human approval.
  Nothing in the pipeline publishes to a public site or mirror.

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
- The source is public; build and release artifacts stay private. Distribution
  to testers is a redistribution event and requires the legal checklist.
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
  host/address/service-hint display;
- a pcap capture/review extension with a user-started VpnService or non-root
  helper contract, a persistent capture indicator, offline pcap/pcapng
  summaries, sensitive-payload warnings, and fixture-only tests;
- a conservative private mobile defaults baseline with a setup checklist and a
  read-only diagnostic covering telemetry, background services, offensive
  tooling, permissions, USB/Wi-Fi/Bluetooth exposure, lock-screen behaviour,
  sensor indicators, and the Padilha UX review.

The boot animation, system font, system UI, lock screen, and default-app
preinstallation still require a system image and a new ADR. Verified boot,
signing, and security-critical UI are unchanged. See
[overlay and build boundaries](docs/branding/overlay-and-build.md) and the
[stock-device preview](docs/branding/preview.md).

## Documentation

- [ADR 0001: GrapheneOS base, device support, and Padilha branding](docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md)
- [Device support matrix and flashing runbook](docs/device-support-and-flashing.md)
- [Attribution, trademark, and redistribution rules](docs/legal/grapheneos-aosp-attribution.md)
- [Padilha look-and-feel scope](docs/branding/padilha-look-and-feel.md)
- [Overlay and system-build boundaries](docs/branding/overlay-and-build.md)
- [Stock-device preview](docs/branding/preview.md)
- [Private release and signing pipeline](docs/release-pipeline.md)
- [Release checklist](docs/release-checklist.md)
- [Security panel contract and safety boundaries](docs/security-panel.md)
- [Private mobile defaults and GrapheneOS invariants](docs/private-mobile-defaults.md)
- [Private mobile setup checklist](docs/setup-checklist.md)
- [Local-network inventory contract, ranges, and helper](docs/local-network-inventory.md)
- [Pcap capture and review contract, warnings, and helper](docs/pcap-capture-review.md)
- [Asset provenance](docs/branding/asset-provenance.md)
- [Machine-readable design tokens](docs/branding/tokens.json)

## Planned surface

- Padilha launcher with app drawer, local search, folders, widgets, work-profile
  support, and accessible light/dark themes
- original wallpaper, palette, icon pack, and typography inside Castela apps
- a dedicated local security panel with authorized lab mode (front-end
  implemented in `preview/security/`; the signed app remains a build task)
- local network inventory with private/link-local range validation and an
  explicit Termux/native helper (front-end contract implemented)
- pcap capture/review with explicit consent, a persistent indicator, offline
  pcap/pcapng summaries, and a documented non-root review helper (front-end
  contract implemented; permission/integrity audits remain planned)
- a private mobile defaults baseline, setup checklist, and read-only diagnostic
  with no telemetry, no unnecessary background services, and no default
  offensive tooling at boot (implemented as policy and tooling)
- no automatic scanning, no hidden privileged service, no root, no telemetry
- a setup companion that checks compatibility and links to the official
  GrapheneOS installation and update documentation

Out of scope for this phase: installing or replacing the boot animation, system
font replacement, system UI theming, preinstalled default apps, Castela ROM
builds, Castela system-image or OTA releases, and automated bootloader unlocking
or device flashing. The [device support and flashing
runbook](docs/device-support-and-flashing.md) documents the manual,
official-GrapheneOS-only path; this repository does not execute it. The boot
animation source in this repository is for a future system-image track only.

## Safety and privacy

No Castela system image exists. Do not flash a Castela image or a custom ROM.
The only supported device path is official GrapheneOS followed by signed Castela
apps; follow the [device support and flashing
runbook](docs/device-support-and-flashing.md) and the official GrapheneOS
instructions. Unlocking the bootloader erases data and has security
consequences, and the bootloader must be locked again before the device is used.
No device has been flashed or validated by this repository. Do not publish builds
or artifacts; the source is public, while release artifacts and signing keys
remain private. The release pipeline rejects public or anonymous artifact stores
and requires a named human approval before a signing key is used. Do not claim
this is official GrapheneOS.

The security panel is an ordinary app. It does not provide kernel, baseband, or
privileged visibility, and it must not claim to. Packet captures may contain
personal data: capture only on networks you own or are authorized to test, keep
data local, and delete it when finished. Live capture is user-started with a
persistent indicator, never starts on first launch, and uses a VpnService or an
explicit non-root helper provider. The local-network inventory accepts only
private/link-local ranges, requires an explicit ownership confirmation before
any provider runs, and never probes ports, exploits services, or captures
credentials.

The private mobile defaults are conservative and battery-safe: no telemetry, no
unnecessary background services, and no default offensive tooling at boot.
Verified boot, SELinux enforcing mode, and app sandboxing remain GrapheneOS
responsibilities and must not be weakened. Permission defaults, USB, Wi-Fi, and
Bluetooth exposure, lock-screen behaviour, and sensor indicators are reviewed in
[the private mobile defaults policy](docs/private-mobile-defaults.md) and the
[setup checklist](docs/setup-checklist.md). The diagnostic script is read-only;
it does not run privileged commands or automatic suspend/reboot tests.

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

## Support

Maria Padilha is free software under GPL-3.0-only. Donations are optional and
never unlock features or hold back builds. See [SUPPORT.md](SUPPORT.md) or
[sponsor development on GitHub](https://github.com/sponsors/Mateus-M-Reis).
