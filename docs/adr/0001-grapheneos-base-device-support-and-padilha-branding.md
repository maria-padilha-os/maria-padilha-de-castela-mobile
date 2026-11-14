# ADR 0001: GrapheneOS base, device support, and Padilha branding

- **Status:** Accepted
- **Date:** 2026-11-06
- **Deciders:** Castela Mobile maintainers
- **Consulted:** Legal and privacy review (external counsel review still required
  before any distribution)
- **Supersedes:** None
- **Related:** [Padilha look-and-feel scope](../branding/padilha-look-and-feel.md),
  [attribution, trademark, and redistribution rules](../legal/grapheneos-aosp-attribution.md)

## Context

`maria-padilha-de-castela-mobile` is meant to be a private cybersecurity mobile
experience with the look and feel of Maria Padilha. The open question is how
much of GrapheneOS we own:

1. **A full GrapheneOS fork and build**, where Castela ships its own signed
   system image and OTA updates; or
2. **A device-side Padilha overlay plus companion apps** installed on top of an
   official GrapheneOS release, where GrapheneOS remains the operating system.

The choice affects build infrastructure, signing and key custody, update
mechanics, the Pixel support matrix, maintenance staffing, security guarantees,
and legal exposure. It must be made before application code or release
automation is designed, because the two options have different trust boundaries
and different artifact pipelines.

This repository must remain private, and its build and release artifacts must
remain private. This ADR does not authorize a ROM build, a device flash, or a public
release. It records the architecture decision and the rules that follow from it.

## Decision

**Adopt option 2: a device-side Padilha overlay and companion apps on top of a
stock, official GrapheneOS release.**

**Reference device: Pixel 9a (`tegu`), unlocked only for the official GrapheneOS
installation and then locked for use and release validation, running the current
stable GrapheneOS release.**

Concretely:

- GrapheneOS remains the operating system and the provider of system updates.
- Castela ships only its own Android applications and design assets: a launcher,
  a theme/icon/wallpaper layer, a local security panel, and an optional setup
  companion.
- No GrapheneOS fork, system image, OTA server, or bootloader unlock flow is
  built in this phase.
- The product is presented as **Castela Mobile, an independent project that runs
  on GrapheneOS** — never as GrapheneOS, an official GrapheneOS build, or an
  "unofficial build" of GrapheneOS.
- The repository and artifacts stay private. Any distribution to testers is a
  redistribution event and requires the legal review described in the linked
  legal rules.

**Documentation addendum (2026-11-14).** The
[device support and flashing runbook](../device-support-and-flashing.md) now
documents the manual, official-GrapheneOS-only path onto a supported Pixel,
including bootloader-unlock warnings, backup, preflight checks, flashing, and
recovery. It is documentation for installing official GrapheneOS followed by
signed Castela apps, not a Castela system image. No repository script unlocks,
erases, or flashes a device.

A full fork is not rejected forever. It is deferred until the triggers in
[Revisit triggers](#revisit-triggers) are met and a new ADR approves it.

## Constraints and non-goals

- **Private by default.** No public repository, public artifact host, public
  release channel, or public screenshots containing signing material.
- **No false affiliation.** "GrapheneOS" and its logo are trademarks of the
  GrapheneOS project. Android and Pixel are trademarks of Google LLC.
- **No ROM build, flash, or release in this task.** The device matrix and
  recovery process must exist before any device is touched.
- **No privileged shortcuts.** No root, no hidden system service, no
  `sharedUserId`, no attempted system-partition modification, and no use of
  private Android APIs.
- **Security is inherited, not reimplemented.** Castela must not become the
  party responsible for delivering monthly Android security patches.
- **The design must remain legible first.** Branding cannot reduce contrast,
  touch-target size, or screen-reader quality.

## Options considered

### Option A — Full GrapheneOS fork and signed build

Castela would sync the GrapheneOS source tree, add a Padilha product layer
(boot animation, system fonts, default apps, system UI theming, settings
branding), generate its own release keys, build per-device factory images and
OTA packages, and run an update server.

This is the only option that can change the boot animation, system font,
system UI, and preinstalled defaults. It also makes Castela responsible for the
entire security update chain.

### Option B — Device-side Padilha overlay and companion apps

The user installs stock official GrapheneOS from the GrapheneOS project, then
installs Castela apps from a private channel. Castela provides:

- a default-home replacement launcher;
- wallpaper, palette, icon, and typography assets delivered through apps;
- a local security panel that uses public Android APIs;
- an optional setup companion that explains compatibility and links to the
  official GrapheneOS installation instructions.

GrapheneOS continues to deliver OS, firmware, kernel, and browser/WebView
updates. Castela delivers only app updates.

### Option C — Hybrid: B now, A later

This is not a separate implementation so much as a staging strategy: ship B,
keep the system-image work behind a new ADR, and only build A if the product
requirements prove that the app layer cannot satisfy them. The recommendation
below is effectively C with B as the committed work and A explicitly deferred.

## Evaluation

The numbers below distinguish **upstream minimums** from **planning budgets**.
Upstream minimums are taken from the GrapheneOS build documentation. Planning
budgets are estimates for this project and must be measured on the actual build
machine before being treated as commitments.

### Build time and disk

| Item | Option A: full fork | Option B: overlay/apps |
| --- | --- | --- |
| Toolchain | AOSP/GrapheneOS build environment: supported Linux distribution, `repo`, 32 GiB RAM minimum, JDK/toolchain, Node.js 24 + yarn for `adevtool` | Android SDK + JDK + Gradle; ordinary developer laptop or small CI runner |
| Source size | 136 GiB with history, or 90 GiB lightweight sync, per GrapheneOS docs | Tens of MB for this repository; SDK/emulator images are the large local item (roughly 15–30 GiB) |
| Build space | 100 GiB+ additional free space for a typical multiarch device build, plus releases, ccache, and signing outputs | APK/AAB outputs are tens of MB; Gradle caches are a few GiB |
| Planning budget | 500 GiB minimum SSD, 1 TiB comfortable; 64 GiB RAM and 16 cores recommended; a clean build can take most of a working day and signing/delta/device validation adds more | 16 GiB RAM is enough; a clean app build is minutes, and a signed release with tests is well under an hour |
| Per-device cost | Each Pixel target needs vendor extraction, a build, and release artifacts; switching targets can force rebuilds | One app build covers every supported Pixel; device testing is the only per-device cost |

The official build requirements are not a suggestion. A 32 GiB machine that
starts swapping during a Chromium/WebView or multiarch build can fail in ways
that look like source corruption. A full fork also needs a CI machine with
enough RAM and disk to rebuild after every upstream security release, not just a
developer laptop.

### Signing and key custody

| Item | Option A: full fork | Option B: overlay/apps |
| --- | --- | --- |
| Keys | Per-device release keys (platform, shared, media, networkstack, Bluetooth, SDK sandbox, GMS compat, NFC), an AVB key, and an SSH key for factory-image signing | One offline app-signing key per app, plus a key for the private update manifest if one is used |
| Blast radius | A lost or leaked OS key compromises verified boot and the update chain for every device using it; rotating it requires a factory reset and a new trust anchor | A leaked app key compromises that app's update chain; rotation is an app-signing problem, not a device-bricking problem |
| Custody | Offline/HSM, encrypted key material, documented ceremony, backup and disaster recovery, separate signing host | Offline/HSM or hardware-backed keystore, documented backup, no keys in CI logs or repository |
| Attestation | Custom keys change the verified-boot trust root; official GrapheneOS attestation and integrity expectations no longer apply | GrapheneOS verified boot and attestation remain intact; Castela apps are ordinary apps |
| Failure mode | A signing mistake can strand users on an unupdatable build or require a wipe | A signing mistake can strand users on an old app version; recovery is a reinstall with the correct key |

For a small team, OS key custody is a permanent operational obligation, not a
one-time setup step. App signing is still sensitive, but it does not put a
device's verified boot at risk.

### OTA and update model

| Item | Option A: full fork | Option B: overlay/apps |
| --- | --- | --- |
| OS updates | Castela must run its own static update server, generate full and delta packages, publish channel metadata, and test upgrades from every supported version | GrapheneOS's updater handles OS, firmware, kernel, and bundled app updates on its normal cadence |
| Initial install | User must unlock the bootloader, flash a Castela factory image, and wipe data; there is no supported OTA path from official GrapheneOS to a differently signed OS | User installs official GrapheneOS using the official web or CLI installer, then installs Castela apps; no bootloader unlock or wipe for app installation |
| App updates | Bundled into the OS image, so every app change is an OS release | Independent signed APK/AAB channel with its own versioning and staged rollout |
| Update server risk | Must never point at the official GrapheneOS update URL with non-official keys; doing so causes repeated failed downloads and effectively attacks the official service | No OS update server; the private app channel is small and can be static |
| Rollback | A/B slot rollback is handled by Android, but the release process must test it; a bad OS release can strand devices | Keep the previous APK and release notes; app rollback is a normal reinstall/downgrade decision |
| Operational load | Release engineering, delta generation, channel promotion, monitoring, and incident response for every device | Upload signed APKs, publish metadata/checksums, and announce the version |

Option A's OTA burden is not just storage. Every release needs an upgrade-path
test from the previous release, a delta test, and a recovery plan. Option B
inherits GrapheneOS's tested update path and keeps Castela's release surface
small.

### Supported Pixel devices

GrapheneOS officially supports Pixel 6 through Pixel 10 as of this ADR, including
the Fold and Tablet targets. Option A would have to build and test every target
it claims to support, because device support code, firmware, kernel, and
per-device testing are all separate work.

Option B can run on any device that GrapheneOS officially supports and that
meets the app's minimum SDK. Castela still needs a validation matrix, but it can
choose a small set of representative devices instead of maintaining one build
per codename.

The full matrix and end-of-support dates are in
[Reference device and support matrix](#reference-device-and-support-matrix).

### Maintenance burden

**Option A** carries the full downstream-maintenance load:

- monthly Android Security Bulletin integration and GrapheneOS release rebases;
- quarterly/yearly AOSP changes and vendor branch updates;
- kernel, firmware, driver, and device-specific security fixes;
- Chromium/Vanadium and WebView updates;
- per-device build, boot, camera, telephony, and update testing;
- release signing, key rotation, update-server operations, and incident response.

A realistic planning estimate is **1.5–3 full-time engineers** plus release
operations, and that is optimistic for a project that also wants to build a
security panel. The repository's current GPL-3.0-only policy adds a further
constraint: GPLv3 code in a locked system image is the kind of installation-
information problem GrapheneOS deliberately avoids. Bundling the Castela app
suite into a system image would need a licensing review before it is attempted.

**Option B** carries only app-layer maintenance:

- tracking Android API level changes and GrapheneOS behavior changes;
- testing the launcher against GrapheneOS's default-home and permission model;
- maintaining the security panel's parsers, permission checks, and UI;
- keeping dependencies patched and the app signing/update channel healthy.

A planning estimate is **0.25–0.5 full-time engineer**, with spike work during
new Android releases. This is compatible with a small project that must also
produce design assets and documentation.

### Security and privacy

Option A's security value depends entirely on Castela's ability to apply
upstream patches faster and more reliably than GrapheneOS. That is unlikely for
a small team, and any delay makes users less safe than if they had stayed on
official GrapheneOS. Custom verified-boot keys also break the official
attestation story: the device can still be secure, but it cannot be presented as
an official GrapheneOS device and some integrity checks will correctly report a
different signer.

Option B keeps GrapheneOS's patch cadence, verified boot, hardware-backed
keystore, and attestation. The new attack surface is the app suite. That surface
must be designed carefully:

- no root, no hidden privileged service, no `sharedUserId`;
- no automatic scanning; capture and inventory start only on explicit user
  action;
- `VpnService` only for user-initiated local capture, with a persistent
  notification and a clear stop control;
- pcap and inventory data stored app-privately, never uploaded, and deletable;
- least-privilege permissions, minimal exported components, and no telemetry.

The security panel must not imply that it provides kernel-level or baseband
visibility. It sees what a normal Android app can see, plus what the user
explicitly grants through the VPN service or usage-access settings.

### Legal and redistribution exposure

Option A distributes a derivative operating system. That triggers:

- GrapheneOS trademark rules and a required rebrand;
- Apache-2.0 NOTICE and modification-marking obligations for AOSP components;
- MIT notice obligations for GrapheneOS-originated code;
- GPL-2.0 source and license obligations for the Linux kernel and other GPL
  components;
- proprietary vendor firmware/blob terms that may prohibit redistribution;
- export, privacy, and security-disclosure review for a device image.

Option B distributes only Castela's own apps and their bundled libraries and
assets. It does not redistribute the GrapheneOS operating system, AOSP system
binaries, or vendor blobs, and it does not need to reproduce the OS source.
AndroidX and other app dependencies still carry their own notices. Trademark use
is limited to a descriptive reference to the compatible base. This is a
materially smaller legal surface.

The details are in
[attribution, trademark, and redistribution rules](../legal/grapheneos-aosp-attribution.md).

### Brand depth

| Surface | Option A | Option B |
| --- | --- | --- |
| Wallpaper | Yes | Yes |
| Palette | Yes | Yes, within Castela apps and launcher |
| Fonts | System-wide | App/launcher only; system font unchanged |
| Icons | System-wide including system UI | Launcher, icon pack, and Castela apps |
| Launcher | Preinstalled default | User-installed default-home replacement |
| Boot animation | Replaceable | **Not replaceable**; stock GrapheneOS animation remains |
| System UI / Settings | Themed | Not themed |
| Default apps | Preinstalled | User installs and chooses defaults |
| OTA branding | Castela-controlled | GrapheneOS-controlled |

Option B delivers most of the visible identity. The missing pieces are the boot
animation, the system font, and system UI chrome. Those are precisely the pieces
that require ownership of the system image, and they are not worth the security
and maintenance cost for this phase.

### Comparison summary

| Criterion | Option A | Option B | Fit for Castela |
| --- | --- | --- | --- |
| Time to first usable artifact | Weeks to months | Days | B |
| Build cost per release | Hours to days | Minutes | B |
| Disk and CI cost | High (hundreds of GiB, 32–64 GiB RAM) | Low | B |
| Signing and key custody | OS keys, AVB, OTA, high risk | App keys, lower risk | B |
| OTA ownership | Full update server and delta pipeline | GrapheneOS owns OS updates | B |
| Device coverage | One build and test matrix per Pixel | Any supported Pixel; test a subset | B |
| Maintenance | 1.5–3 FTE planning estimate | 0.25–0.5 FTE planning estimate | B |
| Security patch cadence | Castela's responsibility | GrapheneOS's responsibility | B |
| Verified boot/attestation | Custom trust root | GrapheneOS trust root intact | B |
| Brand depth | Full, including boot and system UI | High, but no boot/system font/system UI | A only if those are must-haves |
| Legal exposure | High | Low to moderate | B |

## Recommendation

Adopt **Option B** and build a private, app-layer Padilha experience on official
GrapheneOS. Use **Pixel 9a (`tegu`)** as the single reference device.

The deciding factors are, in order:

1. **Security.** GrapheneOS is better at delivering its own security updates than
   a small derivative team will be. Forking would trade a proven update chain for
   one we cannot yet operate.
2. **Maintenance.** A full fork is a permanent release-engineering commitment.
   The app layer lets the project spend its limited time on the launcher,
   security panel, and design rather than on kernel and firmware integration.
3. **Legal.** Not redistributing the OS avoids vendor-blob, GPL source-offer, and
   derivative-branding problems that are disproportionate to the branding gain.
4. **Brand coverage.** The launcher, wallpaper, palette, icons, and app typography
   cover the surfaces users see most. The boot animation and system font are the
   only meaningful gaps, and they do not justify owning an OS.
5. **Reversibility.** Option B can grow into a fork later. Option A cannot easily
   shrink back to an app suite after users depend on its update channel.

## Reference device and support matrix

### Reference device: Pixel 9a (`tegu`)

| Attribute | Value |
| --- | --- |
| GrapheneOS build target | `tegu` |
| Launch | April 2025 |
| OEM minimum support end | April 2032 (7 years) — per GrapheneOS FAQ |
| Memory/storage | 8 GiB RAM; 128/256 GiB storage |
| Security features relevant here | ARM MTE, verified boot, StrongBox, hardware key attestation, per-app network permission |
| Why it is the reference | Official GrapheneOS target; long support window; mid-range price; unlockable; 8 GiB is enough to enforce a realistic app memory budget |
| Purchase rule | Buy an unlocked, non-carrier-locked device; carrier locks can prevent installing GrapheneOS |

The 8 GiB reference is deliberate. The security panel must stream pcap review
from storage, cap its resident memory, and degrade gracefully on 8 GiB devices.
A 12 GiB device is not an excuse to design an app that only works on 12 GiB.

The Pixel 9a is preferred over the base Pixel 9 because the 9a has a longer
minimum support window (April 2032 versus August 2031) at a lower price, and the
app suite does not need the extra memory for its core functions. The Pixel 10a
has a longer window (March 2033) and becomes the next reference when the 9a is no
longer readily available or its support window approaches its end.

### Supported-device matrix

The matrix below reflects GrapheneOS official support and OEM minimum support
dates published at the time of this ADR. Re-check it every six months; a device
that is still sold is not necessarily still supported.

| Device | Codename | OEM minimum support end | Castela role |
| --- | --- | --- | --- |
| Pixel 9a | `tegu` | April 2032 | **Reference and primary validation** |
| Pixel 8a | `akita` | May 2031 | Secondary validation (minimum practical spec) |
| Pixel 8 | `shiba` | October 2030 | Compatibility testing |
| Pixel 8 Pro | `husky` | October 2030 | Compatibility testing |
| Pixel 9 | `tokay` | August 2031 | Compatibility testing |
| Pixel 9 Pro | `caiman` | August 2031 | Compatibility testing |
| Pixel 9 Pro XL | `komodo` | August 2031 | Compatibility testing |
| Pixel 9 Pro Fold | `comet` | August 2031 | Best-effort foldable layout |
| Pixel 10 | `frankel` | August 2032 | Compatibility testing |
| Pixel 10 Pro | `blazer` | August 2032 | Compatibility testing |
| Pixel 10 Pro XL | `mustang` | August 2032 | Compatibility testing |
| Pixel 10 Pro Fold | `rango` | October 2032 | Best-effort foldable layout |
| Pixel 10a | `stallion` | March 2033 | Future reference; compatibility testing |
| Pixel 7 | `panther` | October 2027 | Legacy best-effort |
| Pixel 7 Pro | `cheetah` | October 2027 | Legacy best-effort |
| Pixel 7a | `lynx` | May 2028 | Legacy best-effort |
| Pixel 6 | `oriole` | October 2026 | End of support at ADR date; no guarantee |
| Pixel 6 Pro | `raven` | October 2026 | End of support at ADR date; no guarantee |
| Pixel 6a | `bluejay` | July 2027 | Legacy best-effort |
| Pixel Fold | `felix` | June 2028 | Best-effort foldable layout |
| Pixel Tablet | `tangorpro` | June 2028 | Best-effort tablet layout |

Rules:

- A device is supported only if **GrapheneOS officially supports it**. Do not
  recommend generic system images, non-Pixel ports, or devices that only build
  at source level.
- "Compatibility testing" means the app suite is expected to install and pass
  smoke tests. It does not mean every layout has been tuned for that device.
- "Legacy best-effort" means no performance or long-term support promise; the
  device may already be past its OEM support window.
- Foldables and tablets require explicit layout review; do not assume a phone
  layout scales.
- The reference device must run a **locked-bootloader, official GrapheneOS
  stable** build for release validation. Rooted or unlocked test devices are
  development-only and must not be used to sign off a release.

## Architecture of the recommended approach

### Components

| Component | Responsibility | Trust boundary |
| --- | --- | --- |
| `Padilha Launcher` | Default home, app drawer, search, folders, widgets, icon-pack application, work-profile badge | Ordinary app using `LauncherApps`, `AppWidgetHost`, and public intents; no privileged permissions |
| `Padilha Theme` | Wallpaper picker, palette/typography assets, icon pack, light/dark token selection | Ordinary app using `WallpaperManager` and its own resources; no RRO or system theming |
| `Padilha Security Panel` | User-initiated local network inventory, pcap/pcapng review, permission and integrity audits, export/delete | Ordinary app; `VpnService` only while the user runs a capture; `UsageStatsManager` only with user-granted access; no root or hidden service |
| `Padilha Setup` | Compatibility check, onboarding, link to official GrapheneOS install/update documentation, privacy explanation | Ordinary app; no flashing, no automatic downloads, no bootloader commands |
| `Padilha Design` | Shared Compose theme, tokens, icons, typography, accessibility checks | Library code; no runtime privilege |

The apps are separate packages with separate signing keys unless a future ADR
documents a shared-key exception. They do not use `android:sharedUserId`. Any
inter-app communication uses explicit, signature-checked intents or a
permission-protected content provider, not implicit broadcasts.

### Permissions and security boundaries

- Request permissions at the moment of use, with a plain-language explanation.
- The security panel's core inventory features must work without the VPN
  service. Capture is an explicit, separate action with a persistent
  notification and a stop button.
- Do not request `QUERY_ALL_PACKAGES` for the launcher; use `LauncherApps`.
- Do not request `MANAGE_EXTERNAL_STORAGE`. Use the Storage Access Framework for
  user-selected pcap files and exports.
- No analytics, crash reporting, or telemetry SDKs by default. If crash reports
  are ever added, they must be opt-in, redacted, and documented in a privacy
  notice.
- The security panel stores data in app-private storage and offers a verified
  delete. Exported files are the user's responsibility and carry a warning that
  packet captures may contain personal data.
- Release builds set `android:debuggable="false"`, disable backup for sensitive
  data, and do not include debug-only exported components.

### Build and release pipeline

- Kotlin, Jetpack Compose, Gradle with a pinned JDK and Android SDK.
- Version catalogs, dependency locking, and dependency verification for
  reproducible dependency resolution.
- A software bill of materials (SBOM) and SHA-256 checksums for every release.
- Lint, unit tests, and instrumentation smoke tests on the Pixel 9a reference
  device before promotion.
- Private CI with least-privilege access. Signing happens in an isolated job with
  short-lived credentials; keys are never available to pull-request jobs and
  never printed.
- Release artifacts are stored in a private, access-controlled location with
  retention and audit logs. No public release links.
- Each app has a monotonic `versionCode` and a documented `versionName`; release
  notes state the minimum GrapheneOS/Android version and any migration notes.

### Signing

- Generate one offline release key per app. Store it in an HSM or an encrypted
  offline location with a documented backup and recovery procedure.
- Verify every release with `apksigner verify --print-certs` and record the
  certificate digest in the release record.
- Do not reuse the debug key. Do not check keystores, `.p12`, `.pem`, or `.jks`
  files into the repository; `.gitignore` covers the common extensions.
- If app-signing key rotation is needed, plan the upgrade path before shipping
  the rotated key; old clients must still be able to verify the update.
- The private update manifest, if used, is signed with a separate key and
  delivered over TLS with certificate pinning.

### Update model

- **OS/firmware/kernel/browser:** delivered by GrapheneOS's updater. Castela does
  not proxy, mirror, or re-sign these updates.
- **Castela apps:** delivered through a private signed channel. The channel
  publishes the APK/AAB, checksum, SBOM, version metadata, and signature
  fingerprint. A staged rollout is preferred over immediate broad release.
- **Rollback:** keep the previous APK and release notes. Do not rely on Android
  downgrade behavior; document the supported recovery path.
- **Compatibility:** the setup companion checks the GrapheneOS version and warns
  when the device is outside the supported matrix. It links to official
  installation and update instructions rather than reproducing them.

### Repository and artifact privacy

- The repository stays private. Do not push this branch to a public remote.
- Build outputs, release bundles, keys, device images, and signing logs are
  ignored by Git and stored only in the private artifact store.
- Testers receive time-limited, authenticated access. A download link is not
  "private" if it is unauthenticated or forwarded publicly.
- Before any distribution, confirm that the recipient list, license obligations,
  and export/privacy review are documented.

## Legal summary

This section is a summary, not legal advice. The operative rules are in
[attribution, trademark, and redistribution rules](../legal/grapheneos-aosp-attribution.md).

| Topic | Rule |
| --- | --- |
| GrapheneOS code license | GrapheneOS's own standalone projects are MIT; forks of upstream projects inherit the upstream license. The OS as a whole is not MIT. |
| AOSP license | Most AOSP userspace is Apache-2.0; the Linux kernel is GPL-2.0 (with system exceptions); other components have per-file licenses. |
| Attribution | Keep copyright, license, and NOTICE files; mark modified files; include license texts; provide corresponding source for GPL components when distributing binaries. |
| GrapheneOS trademark | The name and logo are trademarks of the GrapheneOS project (US serial numbers 90746220 and 90746226). Derivatives must replace GrapheneOS branding and be clearly distinct. Do not use the logo or wordmark as product branding. |
| "Unofficial build" | Only a build of official GrapheneOS sources with the update URL changed may be called an unofficial build. Castela is not that; it is a distinct project that runs on GrapheneOS. |
| Android/Pixel marks | "Android", the Android logo, "Google Play", and "Pixel" are Google LLC trademarks, not AOSP assets. Use the names only descriptively; do not use logos or imply certification, partnership, or endorsement. |
| Vendor blobs | Pixel firmware and vendor files are proprietary and may not be redistributable. This is another reason a full ROM stays private and requires legal review. |
| App licenses | Castela's original code is GPL-3.0-only per repository policy. Third-party dependencies and assets keep their own licenses; record them in the SBOM and NOTICE. |
| Testers | Distribution to testers is distribution. Complete the pre-release checklist before sending builds outside the maintainer group. |

## Padilha look-and-feel summary

The detailed specification and tokens are in
[Padilha look-and-feel scope](../branding/padilha-look-and-feel.md). The
machine-readable palette and contrast pairs are in
[`tokens.json`](../branding/tokens.json).

| Surface | Scope in Option B | Scope in a future Option A |
| --- | --- | --- |
| Wallpaper | Original Padilha artwork, dark and light variants, responsive crops, no text or third-party marks | Same, plus system wallpaper preload |
| Palette | Plum/night, candle gold, wine, rose, cream; semantic success/warning/danger colors; tested contrast | Same, plus system UI accents |
| Fonts | Fraunces (display) and Inter (UI/body) inside Castela apps; OFL 1.1; no system font replacement | Same, plus system-wide font |
| Icons | 24 dp grid, 2 dp stroke, adaptive and monochrome themed icons; Material Symbols or original icons under Apache-2.0 | Same, plus system icon coverage |
| Launcher | Default-home replacement with app drawer, search, folders, widgets, work profile, accessibility | Preinstalled default launcher |
| Boot animation | **Out of scope.** Stock GrapheneOS animation remains; do not root or modify `/system` to fake it. Use a first-run setup moment instead. | In scope, with a separate system-image ADR and a tested `bootanimation.zip` |
| Light/dark legibility | WCAG 2.2 AA: 4.5:1 for body text, 3:1 for large text, icons, and UI boundaries; 200% text; TalkBack; reduced motion; no color-only status | Same, plus system-wide verification |

Brand rules that apply immediately:

- The product name is **Castela Mobile**. Do not use "GrapheneOS" in the product
  name, launcher label, app name, icon, or domain.
- Use the sentence "Castela Mobile is an independent project that runs on
  GrapheneOS." Do not use the GrapheneOS logo.
- Do not use the Android robot, Google Play badge, or Pixel logo.
- Original artwork only. Do not use third-party images, celebrity likenesses, or
  sacred/religious symbols as decoration without context and review.
- Fonts must be OFL/Apache-2.0 compatible and shipped with their license texts.

## Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Expectation mismatch: users expect a full ROM with a custom boot animation | High | Medium | State the scope in README, setup, and release notes; show the app-layer experience; never imply a custom boot animation |
| GrapheneOS changes launcher/default-home or permission behavior | Medium | Medium | Test against GrapheneOS stable every release; use public APIs; keep a compatibility shim and a tested fallback |
| Security panel is mistaken for a privileged or kernel-level tool | Medium | High | Plain-language capability text; no root claims; show exactly what is visible; user-initiated capture only |
| pcap or inventory data leaks personal information | Medium | High | App-private storage, explicit export warning, delete control, no telemetry, no cloud sync |
| App signing key compromise or loss | Low | High | Offline/HSM storage, documented backup, rotation plan, isolated signing job, incident runbook |
| Trademark or attribution mistake in copy or assets | Low | High | Legal checklist, disclaimer in README/About, no logos, review before release |
| Private repository or artifact leak | Medium | High | Private remote, access control, secret scanning, `.gitignore`, no public links, audit logs |
| GPLv3 app code later bundled into a locked system image | Low now, high later | High | Keep apps user-installed; new ADR and legal review before any system-image work |
| Reference device reaches end of support | Certain (April 2032) | Medium | Re-review the matrix every six months; plan Pixel 10a as the next reference |
| Upstream GrapheneOS policy or support change | Low | Medium | Monitor release notes and FAQ; keep the app layer portable to another Android base if needed |

## Revisit triggers

Do not start a full fork merely because the app layer is inconvenient. Start a
new ADR only if one or more of these is true:

1. A custom boot animation, system font, system UI theme, or preinstalled default
   app is a **hard product requirement**, not a nice-to-have.
2. The security panel needs privileged APIs, kernel/eBPF visibility, raw socket
   capture, or another capability that a normal app plus `VpnService` cannot
   provide.
3. Castela must ship preinstalled devices or an OTA image to users who will not
   install apps themselves.
4. The team has at least two ROM/release engineers, a signing/HSM ceremony, a
   1 TiB-class CI machine, and a legal review that clears vendor-blob and GPL
   obligations.
5. GrapheneOS changes its licensing, trademark policy, or device support in a
   way that breaks the app-layer approach.
6. The app-layer experience fails measured usability or security goals on the
   reference device and the failure cannot be fixed within the app sandbox.

## Consequences

**Positive**

- GrapheneOS remains responsible for security patches, firmware, kernel, and
  verified boot.
- The project can ship useful artifacts in days rather than months.
- Legal exposure stays small: no OS redistribution, no vendor blobs, no
  GrapheneOS trademark in the product name.
- The app suite can iterate independently of OS releases.
- The reference device has a support window through April 2032.

**Negative**

- No custom boot animation, system font, or system UI theming.
- The launcher must be installed and selected by the user; it cannot be
  preinstalled.
- Some security-panel features are constrained by the Android app sandbox.
- The product is an experience layer, not a standalone OS image. Marketing and
  documentation must say so.
- A future fork would require a new ADR, new keys, new build infrastructure, and
  a migration plan.

**Neutral**

- The OS update channel and the app update channel are separate.
- The reference device is a Pixel, so the project remains dependent on Google's
  Pixel support window even though it does not depend on Google services.

## Out of scope

- Building, flashing, or releasing a Castela ROM or system image.
- Generating or storing OS signing keys, AVB keys, or OTA metadata.
- Providing automated bootloader-unlock or device-flashing scripts. The manual
  official-GrapheneOS runbook is documentation only; it does not authorize a
  Castela image.
- Shipping actual app code, design binaries, or wallpapers in this task.
- Public release, public repository mirror, or public artifact hosting.
- Legal advice. The linked legal rules are an engineering policy and must be
  reviewed by counsel before distribution.

## Follow-up work

1. Obtain legal review of the linked attribution/trademark/redistribution rules.
2. Add a top-level `LICENSE` file that matches the repository's GPL-3.0-only
   policy, and a `NOTICE`/third-party license process for app releases.
3. Write app-specific ADRs for the launcher, security panel, and update channel.
4. Produce original wallpaper, icon, and wordmark assets with provenance records.
5. Stand up a private CI and artifact store; verify no keys or builds are
   reachable without authentication.
6. Acquire an unlocked Pixel 9a and validate the official GrapheneOS install and
   the app smoke-test matrix before any tester distribution.
7. Review the device matrix and GrapheneOS support dates every six months.

## References

Accessed 2026-11-06.

- GrapheneOS build requirements, supported targets, signing, and update server:
  <https://grapheneos.org/build>
- GrapheneOS FAQ: supported devices, support lifetime, licensing, and trademark:
  <https://grapheneos.org/faq#supported-devices>,
  <https://grapheneos.org/faq#device-lifetime>,
  <https://grapheneos.org/faq#copyright-and-licensing>,
  <https://grapheneos.org/faq#trademark>
- GrapheneOS source and project layout: <https://grapheneos.org/source>
- GrapheneOS releases: <https://grapheneos.org/releases>
- GrapheneOS usage and update model: <https://grapheneos.org/usage#updates>
- AOSP licenses: <https://source.android.com/docs/setup/about/licenses>
- Apache License 2.0: <https://www.apache.org/licenses/LICENSE-2.0>
- GNU GPL version 2: <https://www.gnu.org/licenses/old-licenses/gpl-2.0.html>
- MIT license: <https://opensource.org/license/mit>
- Android brand guidelines: <https://developer.android.com/distribute/marketing-tools/brand-guidelines>
- WCAG 2.2: <https://www.w3.org/TR/WCAG22/>
