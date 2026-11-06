# GrapheneOS/AOSP attribution, trademark, and redistribution rules

- **Status:** Engineering policy; legal review required before distribution
- **Date:** 2026-11-06
- **Applies to:** `maria-padilha-de-castela-mobile` and all Castela Mobile
  artifacts
- **Decision record:** [ADR 0001](../adr/0001-grapheneos-base-device-support-and-padilha-branding.md)

This document is **not legal advice**. It translates the upstream licenses and
trademark statements into rules the project can follow. A qualified lawyer must
review the rules and the specific release before anything is distributed outside
the maintainer group.

## 1. Scope and baseline

Castela Mobile is an independent project that runs on GrapheneOS. It is **not**
GrapheneOS, **not** an official GrapheneOS build, and **not** an "unofficial
build" of GrapheneOS as that term is used upstream. The chosen architecture
ships only Castela applications and their bundled libraries and assets; it does
not redistribute the GrapheneOS operating system.

Two separate things are often confused:

- **Copyright licenses** govern code and content: MIT, Apache-2.0, GPL-2.0,
  OFL, BSD, and others.
- **Trademark rights** govern names, logos, and source identifiers. A code
  license does not grant trademark permission.

A permissive code license does not mean the GrapheneOS name or logo can be used
as product branding. Conversely, a trademark policy does not override the
copyright license for the code.

## 2. Upstream licensing map

| Component | Typical license | What it means for Castela |
| --- | --- | --- |
| GrapheneOS-originated standalone projects | MIT | If code is copied or modified, keep the copyright and MIT permission notice. |
| GrapheneOS forks of AOSP projects | Upstream license inherited (commonly Apache-2.0) | Treat the file's existing license as authoritative; do not assume the whole tree is MIT. |
| AOSP userspace | Mostly Apache-2.0; some BSD, MIT, and other OSI licenses | Keep copyright, license, and NOTICE material; mark modifications; include the license text. |
| AndroidX/Jetpack libraries bundled in APKs | Mostly Apache-2.0, with per-library exceptions | Include the license/NOTICE material and record the dependency in the SBOM. |
| Linux kernel and GPL components | GPL-2.0 (with system exceptions where applicable) | If binaries are distributed, provide the complete corresponding source, build/install scripts, and license text, and do not add restrictions. |
| LLVM/compiler-rt and similar | Apache-2.0 with LLVM exceptions, or per-file terms | Keep the applicable notices and exception text. |
| Chromium/Vanadium and WebView | BSD-style and other per-file licenses | Keep notices; do not strip license files from bundled components. |
| Pixel firmware, vendor blobs, factory images | Proprietary Google/vendor terms | Do not redistribute separately or in a ROM without written permission and legal review. |
| Fonts (Fraunces, Inter) | SIL Open Font License 1.1 | Ship the OFL text; do not sell the fonts by themselves; if a reserved font name is used for a modified version, rename it as the OFL requires. |
| Icons (Material Symbols or original) | Apache-2.0 (Material Symbols); original icons under project policy | Keep the Apache-2.0 notice; do not use Google or Android logos as icons. |
| Wallpapers and original art | Castela project license (GPL-3.0-only unless noted) | Record the author, source, license, and provenance for every asset. |

The GrapheneOS FAQ states that GrapheneOS's own code is MIT-licensed, that
modifications to upstream projects inherit the upstream license, and that the
project has no copyright assignment. The FAQ also notes that the OS contains
GPLv2 kernel code and other permissively licensed components. Do not describe
"GrapheneOS" as simply "MIT-licensed" without qualification.

## 3. Attribution requirements by license

### Apache-2.0

When redistributing Apache-2.0 code or a work containing it:

- Include a copy of the Apache License 2.0.
- Retain all copyright, patent, trademark, and attribution notices from the
  source, including `NOTICE` files where present.
- Mark modified files and state the changes. A `CHANGES.md` or per-file header
  is acceptable if it is specific.
- Do not use the Apache name, logo, or "Apache" branding to endorse Castela.
- Do not remove the "no trademark license" language from the license text.

### MIT

When redistributing MIT-licensed code:

- Include the original copyright notice and the MIT permission notice in the
  distribution.
- Do not use the copyright holder's name to endorse Castela without permission.

### GPL-2.0 (and other GPL/LGPL components)

Distribution of binaries triggers source obligations. If Castela ever ships a
ROM or a bundled system component:

- Provide the complete corresponding source for the GPL-covered work, including
  modifications, build scripts, and installation scripts.
- Include the full GPL text and any applicable exception text.
- Provide a written offer or a durable download location for the source.
- Do not impose additional terms that restrict the GPL rights.
- For LGPL components, preserve the ability to relink or replace the library as
  the license requires.

Internal private use is not distribution, but **sending a build to a tester is**.
Treat every artifact that leaves the maintainer group as distribution.

### Other licenses

- **BSD:** retain the copyright notice, conditions, and disclaimer.
- **OFL:** include the license text; respect reserved font names; do not sell the
  fonts standalone.
- **Proprietary vendor files:** do not redistribute without a written right to do
  so.
- **Public-domain/CC0:** keep a provenance record even when attribution is not
  legally required.

## 4. Trademark rules

### GrapheneOS

The GrapheneOS FAQ states that the GrapheneOS name and logo are trademarks of
the GrapheneOS project, registered in the United States with serial numbers
**90746220** and **90746226**, and protected in Canada as common-law marks while
registration is pending. The FAQ says derivatives that are published or
redistributed should replace GrapheneOS branding with their own and must be
clearly distinct. It also says only a build of the official GrapheneOS sources
with the update server URL changed may be called an "unofficial build"; anything
with modifications beyond that is a distinct OS based on GrapheneOS.

Rules:

- **Use the name descriptively only** when identifying the platform, for example:
  "Castela Mobile is an independent project that runs on GrapheneOS."
- **Do not use the GrapheneOS logo or wordmark as product branding**, app icon,
  splash screen, launcher label, domain name, or social-media handle.
- **Do not call Castela "GrapheneOS", "GrapheneOS Mobile", "GrapheneOS
  Castela", or an "official GrapheneOS" product.**
- **Do not call Castela an "unofficial GrapheneOS build."** It is not a build of
  the official sources with only the update URL changed.
- **Do not imply endorsement, sponsorship, partnership, or certification** by
  the GrapheneOS project.
- Put the disclaimer in the README, the About screen, release notes, and any
  page that mentions GrapheneOS.

The GrapheneOS `branding` repository is MIT-licensed and is described as a stub
for future OS branding, but its code license does not grant permission to use the
GrapheneOS trademarks. Do not copy the logo or wordmark from it.

### Android, Google Play, and Pixel

The Android brand guidelines state that the "Android" name, the Android logo,
the "Google Play" brand, and other Google trademarks are property of Google LLC
and are not assets available through AOSP. Marketing that references Android or
Google trademarks must be reviewed and approved by the Android brand team.

Rules:

- Use "Android" only descriptively, for example "an Android app" or "Android
  APIs". Do not use the Android robot, the Android logo, or the "Powered by
  Android" badge.
- Do not use "Google Play" branding; Castela is not distributed through Google
  Play in this phase.
- "Pixel" is a Google trademark. Use "Pixel 9a" only to identify compatible
  hardware; do not put "Pixel" in the product name, icon, or domain.
- Do not claim Android compatibility, CTS certification, or Google certification.
- Do not use Google or Pixel logos in screenshots, wallpapers, icons, or
  marketing without permission.

### Maria Padilha

Maria Padilha is a figure from Brazilian folklore and Afro-Brazilian religious
traditions. The project name and visual language must be treated with respect.

Rules:

- Use original artwork; do not copy third-party images, costumes, or shrine
  photography.
- Do not depict a specific living person or imply that a religious community or
  entity endorses Castela.
- Avoid using sacred symbols as generic decoration. If a symbol is important to
  the design, document its context and have someone from the relevant community
  review it.
- Do not claim trademark rights in "Maria Padilha" or "Castela Mobile" without a
  clearance search and legal advice.
- Keep a provenance record for every asset: author, source, license, date, and
  any modifications.

## 5. Redistribution scenarios

### A. Maintainers only

No distribution outside the maintainer group. Keep the repository and artifacts
private. Copyright obligations are limited, but the project should still keep
license files and provenance so a later release is not blocked by missing
records.

### B. Private testers

Sending an APK or a build to a tester is distribution. Before the first tester
release:

- include the app's license and third-party notices;
- include the privacy notice and the capture-data warning;
- use authenticated, time-limited access, not a public link;
- record who received which version and when;
- confirm that no OS image, vendor blob, or signing key is in the bundle.

### C. Public app release (not authorized by this ADR)

A public release needs a separate review covering:

- app license compatibility and complete third-party notices;
- privacy policy, data protection (including LGPD/GDPR where applicable), and
  export/dual-use rules for security tooling;
- trademark clearance for the product name and assets;
- store or distribution-channel requirements;
- security disclosure and incident-response contacts.

### D. Full GrapheneOS fork or ROM (not authorized by this ADR)

A full ROM is a derivative operating system and a much larger legal event. It
requires a new ADR and legal review covering at minimum:

- complete rebranding and removal of GrapheneOS name/logo;
- Apache-2.0 NOTICE and modification records;
- GPL source offers and build/install scripts;
- vendor firmware/blob redistribution rights;
- custom verified-boot keys, attestation, and update-chain disclosure;
- privacy, export, and security-response obligations;
- a distribution plan that does not point at the official GrapheneOS update
  server.

### E. Installer scripts and documentation

Linking to official GrapheneOS downloads is acceptable. Do not mirror, rehost, or
re-sign GrapheneOS images. If a script downloads an official image, verify the
official signature or checksum and tell the user what is being downloaded. Do not
embed a bootloader-unlock or flashing procedure in an app without a separate
safety and legal review.

## 6. Signing, verified boot, and attestation

- Castela app signing keys are not GrapheneOS OS keys. Never label an app
  signature as a GrapheneOS signature.
- A custom OS build would use a different verified-boot trust root. It cannot
  pass official GrapheneOS attestation as if it were an official build. Any
  security panel or documentation must show the actual signer, not the official
  GrapheneOS identity.
- Do not use the official GrapheneOS update URL for a non-official build. The
  GrapheneOS build documentation warns that doing so causes repeated failed
  downloads and effectively performs a denial-of-service attack on the official
  service.
- Keep signing keys in an HSM or encrypted offline storage with a documented
  backup. Never commit keys, keystores, `.p12`, `.pem`, `.jks`, or `.pk8` files.

## 7. Privacy and security-tooling rules

- The security panel processes data locally by default. No telemetry, analytics,
  or cloud upload without explicit, informed opt-in.
- Packet captures can contain personal data, credentials, and third-party
  communications. Warn before export, store app-privately, and provide a delete
  control.
- "Authorized lab mode" must require the user to confirm they are authorized to
  capture or inspect the network. Do not ship exploit payloads or attack
  automation.
- Comply with applicable computer-misuse, privacy, and data-protection law. The
  project does not authorize testing on networks the user does not own or have
  permission to test.
- A privacy notice and a security disclosure policy are required before public
  distribution.

## 8. Record-keeping

For every release, keep:

- the SBOM and dependency license list;
- the third-party `NOTICE` bundle and license texts;
- the corresponding-source offer or location for GPL/LGPL components, if any;
- the app signing certificate fingerprint and `apksigner verify` output;
- the artifact SHA-256 checksums and build provenance;
- the tester/distribution log;
- the legal-review sign-off for the release scope.

## 9. Pre-release checklist

- [ ] Product name and copy do not use GrapheneOS, Android, Google Play, or Pixel
      branding as product branding.
- [ ] The "independent project, not official GrapheneOS" disclaimer is present in
      the README, About screen, and release notes.
- [ ] No GrapheneOS, Android, Google Play, or Pixel logo is used.
- [ ] No third-party image, font, icon, or font file lacks a license/provenance
      record.
- [ ] Apache-2.0/MIT/BSD/OFL notices are included where required.
- [ ] GPL/LGPL source obligations are met if any GPL/LGPL binary is distributed.
- [ ] No vendor blob, factory image, or OS image is in the artifact bundle.
- [ ] No signing key, keystore, password, or token is in the repository or logs.
- [ ] Privacy notice and pcap-export warning are present.
- [ ] Tester access is authenticated and time-limited.
- [ ] Legal review is recorded for the release scope.
- [ ] The device matrix and GrapheneOS support dates are current.

## 10. References

Accessed 2026-11-06.

- GrapheneOS FAQ, copyright/licensing and trademark sections:
  <https://grapheneos.org/faq#copyright-and-licensing>,
  <https://grapheneos.org/faq#trademark>
- GrapheneOS build documentation (update server and signing):
  <https://grapheneos.org/build>
- GrapheneOS source:
  <https://grapheneos.org/source>
- AOSP licenses:
  <https://source.android.com/docs/setup/about/licenses>
- Android brand guidelines:
  <https://developer.android.com/distribute/marketing-tools/brand-guidelines>
- Apache License 2.0:
  <https://www.apache.org/licenses/LICENSE-2.0>
- GNU GPL version 2:
  <https://www.gnu.org/licenses/old-licenses/gpl-2.0.html>
- SIL Open Font License 1.1:
  <https://openfontlicense.org/>
- WCAG 2.2:
  <https://www.w3.org/TR/WCAG22/>
