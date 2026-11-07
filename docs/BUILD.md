# Private GrapheneOS build

This directory scaffolds a private, reproducible build on top of GrapheneOS. It
does not contain GrapheneOS source, vendor blobs, signing keys, or release
artifacts. The source tree is synced into the ignored `.scratch/grapheneos`
directory, built locally, signed locally, and never published.

## Selected base

| Item | Value |
| --- | --- |
| Base | GrapheneOS 17 |
| Stable release tag | `2026110200` |
| Signed tag object | `433433b931eeb4a33613a52acc545c08835e5f94` |
| Tag commit | `abed042a17e948a9734e4c3927ce936b5648129f` |
| Manifest | `https://github.com/GrapheneOS/platform_manifest.git` |
| Manifest ref | `refs/tags/2026110200` |
| AOSP baseline | `android-17.0.0_r1` |
| Reference target | `tegu` (Pixel 9a), product `tegu-cur-user` |

The pin lives in [`config/release.env`](../config/release.env). GrapheneOS
stable manifests reference every project by commit hash; verifying the signed
tag therefore locks the whole tree. `repo init -b refs/tags/2026110200` is used
instead of the moving `17` development branch.

`tegu` is the first build target, not a claim that a device has been flashed or
validated. The other supported Pixel targets are listed in
[`config/devices.tsv`](../config/devices.tsv). Emulator targets are development
builds and are not part of this private-release scaffold.

## Host requirements

These are the requirements from the GrapheneOS build guide, applied to this
pin.

| Resource | Requirement |
| --- | --- |
| Architecture | x86_64 Linux |
| Operating system | Arch Linux, Debian 12 (bookworm), Ubuntu 24.04 LTS or 24.10. Ubuntu 24.04 LTS is the recommended CI/build reference. |
| CPU | 8 or more logical cores recommended; more cores reduce build time. |
| RAM | 32 GiB minimum. 64 GiB recommended for a full parallel build. Swap is not a substitute for RAM. |
| Disk | 136 GiB for a standard sync with history, or 90 GiB for a lightweight sync, plus 100 GiB for a typical full build. Budget at least 236 GiB free; 300 GiB is recommended for headroom and repeat builds. |
| Java | No host JDK is required for the OS build. AOSP supplies prebuilt OpenJDK 21 and 25 under `prebuilts/jdk/`; do not override `JAVA_HOME` for the OS build. Standalone app tooling may use a JDK bundled with Android Studio, but that is outside this scaffold. |
| Android SDK | Not required for the OS build. The source provides `prebuilts/sdk` and `prebuilts/build-tools`. A standalone SDK is only for app/CTS work; `adb` and `fastboot` are only for device steps. |
| Network | Required for `sync`; not required for `check`, `build`, or `sign`. |

If standalone app or CTS work needs a separate SDK, use Android command-line
tools `11076708` (SHA-256
`2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258`),
`platform-tools`, `build-tools;36.0.0`, and `ndk;29.0.14206865`. None of these
are used by `./build.sh`, and `ANDROID_HOME` is not needed for the OS build.
`adb` and `fastboot` belong only to the manual device workflow.

Install the distribution packages that provide: `repo`, `python3`, `git`,
`gnupg`, `openssh-client`, `curl`, `rsync`, `unzip`, `zip`, `diffutils`,
`openssl`, `hostname`, freetype/fontconfig and a TrueType font (DejaVu is
fine), Node.js 24 LTS and `yarnpkg` for `adevtool`, `git-lfs`, `gperf`, and the
32-bit glibc/gcc runtime libraries needed by Vanadium. A standalone `repo`
launcher from AOSP is preferable to an old distribution package because it
self-updates and verifies updates with GPG.

The scaffold itself never installs packages and never asks for elevated
privileges. Package installation is an administrator action performed outside
these scripts.

## First build

Run from the repository root:

```sh
./build.sh plan
./build.sh doctor
./build.sh verify-pin --network
./build.sh sync
./build.sh build --device tegu
```

What each step does:

- `plan` prints the pin, requirements and the CI/device split. It is offline.
- `doctor` runs the offline checks and verifies build tools, architecture, RAM
  and free disk. It fails rather than continuing on an undersized host.
- `verify-pin --network` fetches only the small manifest repository, verifies
  the SSH signature with the pinned GrapheneOS allowed-signers key, and checks
  the tag object, commit and AOSP baseline.
- `sync` runs `repo init` at the exact signed tag, installs
  `manifests/castela-local.xml`, re-verifies the tag, and runs `repo sync`.
  Source stays in `.scratch/grapheneos`, inside this checkout and ignored by
  git.
- `build` verifies the source pin again, runs `lunch tegu-cur-user`, and builds
  `target-files-package` plus the documented vendor boot image targets for the
  selected Pixel. It sets `OFFICIAL_BUILD=false` and never signs or publishes.

For a different supported Pixel, pass `--device` to `build` and `sign`, for
example `--device husky`. The product and extra make targets come from
`config/devices.tsv`.

Dry runs print the exact commands without touching the network, source tree, or
device:

```sh
./build.sh sync --dry-run
./build.sh build --device tegu --dry-run
./build.sh sign --build-number 2026110200 --dry-run
```

## Reproducibility

The pin is exact: tag `2026110200`, tag object
`433433b931eeb4a33613a52acc545c08835e5f94`, commit
`abed042a17e948a9734e4c3927ce936b5648129f`. `scripts/verify-pin.sh --network`
re-checks the signature, and `build`/`sign` re-check the synced manifest before
doing any work.

To reproduce a past unsigned build:

1. Use the same tag, tag object and commit recorded in this repository.
2. Export the original `BUILD_DATETIME` and `BUILD_NUMBER`, for example from the
   private build log and `out/build_date.txt` / `out/build_number.txt` in the
   previous output tree. The build script preserves both when set.
3. For a production build, start from an empty `out` directory. Incremental
   builds are for development only.
4. Record the host OS, package versions, CPU count and locale in the private
   build log. They influence the unsigned image even when the source is pinned.

The build script fixes `LANG`, `LC_ALL` and `TZ` to `C`, `C` and `UTC`, and
keeps `OFFICIAL_BUILD=false`. Signed artifacts are reproducible only with the
same private signing keys; never expect a byte-identical signature from a
different key set.

## Vendor blobs and proprietary code

Do not commit vendor images, firmware, `adevtool` output, or proprietary
application blobs. This scaffold does not run `adevtool generate-all` and does
not download device vendor files. If a later build needs Pixel vendor files,
they stay inside the ignored source tree and are never added to this repository.
`scripts/check-no-vendor-blobs.sh` enforces the tracked-file boundary.

## CI and device split

CI can run the offline checks, the test suite, pin validation, and every
`--dry-run` form without a device. Building and signing require a properly
sized build host. Bootloader unlock, factory-image flashing, OTA sideloading and
hardware verification require a physical device and are intentionally not
automated. See [`CI.md`](CI.md) for the detailed split.

## Signing

Signing keys must live outside this checkout. `scripts/check-signing-keys.sh`
checks presence and permissions but never reads or prints key contents. The
`sign` command links the external key store into the ignored source tree, builds
the signing tools, and writes signed artifacts under the ignored source tree.
It does not upload, configure an update server, or publish metadata. See
[`SIGNING.md`](SIGNING.md).

## Out of scope

- Flashing, unlocking, or otherwise modifying a device.
- Downloading or committing proprietary vendor blobs.
- Publishing releases, update metadata, checksums, or download URLs.
- Claiming official GrapheneOS status. This is an independent private project.
