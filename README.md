# Castela Mobile

Public-source cybersecurity mobile image based on GrapheneOS, with the look and
feel of Maria Padilha. **Release builds remain private.**

This is **not official GrapheneOS**. It is a private project that uses the
GrapheneOS/AOSP base and adds a Padilha design overlay plus a security panel.

## Status

**Private build scaffold.** The GrapheneOS base is pinned, the build and signing
entry points exist, and the offline checks run without a device. No ROM has
been published, no proprietary vendor blob is in the repository, and no device
has been flashed.

## Pinned base

| Item | Value |
| --- | --- |
| Base | GrapheneOS 17 |
| Stable release | `2026110200` |
| Signed tag object | `433433b931eeb4a33613a52acc545c08835e5f94` |
| Commit | `abed042a17e948a9734e4c3927ce936b5648129f` |
| AOSP baseline | `android-17.0.0_r1` |
| Reference device | `tegu` (Pixel 9a), product `tegu-cur-user` |

The machine-readable pin is [`config/release.env`](config/release.env). The
upstream manifest is `https://github.com/GrapheneOS/platform_manifest.git` at
`refs/tags/2026110200`; its SSH signature is checked against the pinned
GrapheneOS allowed-signers key before the source is synced.

## Quick start

```sh
./build.sh plan                 # pin and requirements, offline
./build.sh check                # offline CI checks
./build.sh doctor               # verify build host resources
./build.sh verify-pin --network # verify the signed upstream tag
./build.sh sync                 # source into .scratch/grapheneos
./build.sh build --device tegu  # unsigned target-files-package
./build.sh sign --build-number 2026110200  # local only, keys outside repo
./tests/all.sh                  # repository tests
```

`sync`, `build` and `sign` require a build host with at least 32 GiB RAM and
236 GiB free disk. `sync` also needs network access. None of the commands flash
a device, download vendor blobs, or publish artifacts. Device setup and flashing
are manual and intentionally not automated.

## Requirements and documentation

- [Build requirements and reproducibility](docs/BUILD.md) — disk, RAM, Java,
  Android SDK, package list, pinned manifest and build steps.
- [CI and device boundaries](docs/CI.md) — what runs without a device, what
  needs a build host, and what is device-only.
- [Signing key custody](docs/SIGNING.md) — keys outside the repository, the
  metadata-only checker, and local signing.
- [Manifest pin](manifests/README.md) — why the signed upstream tag is the pin
  and how to update it.

## Planned surface

- Padilha wallpaper, palette, fonts, icons, launcher, and boot treatment
- readable light/dark colours with contrast checks
- a dedicated security panel with authorized lab mode
- local network inventory, pcap review, and permission/integrity audits
- no automatic scanning, no hidden privileged service, no telemetry

## Safety

Do not flash a device until the device matrix, recovery documentation, and
signed build pipeline are validated. Do not publish builds; release artifacts
remain private. Do not add vendor blobs, signing keys, public update metadata,
or release downloads to this repository. Do not claim this is official
GrapheneOS.

## Relationship to the other repositories

The Padilha design language and shell work live in
[`maria-padilha-de`](https://github.com/maria-padilha-os/maria-padilha-de).
The normal mobile OS is
[`maria-padilha-mobile`](https://github.com/maria-padilha-os/maria-padilha-mobile).
The desktop cyber image is
[`maria-padilha-de-castela`](https://github.com/maria-padilha-os/maria-padilha-de-castela).
