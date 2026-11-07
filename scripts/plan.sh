#!/usr/bin/env bash
# Print the selected GrapheneOS base, host requirements and command split.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

print_pin

cat <<EOF

Host requirements (see docs/BUILD.md):
  OS:        x86_64 Linux; Ubuntu 24.04 LTS, Debian 12, or Arch Linux
  RAM:       ${CASTELA_MIN_RAM_GIB} GiB minimum, 64 GiB recommended
  Disk:      ${CASTELA_MIN_DISK_GIB} GiB free (sync + build), ${CASTELA_RECOMMENDED_DISK_GIB} GiB recommended
  Java:      no host JDK for the OS build; AOSP supplies prebuilt JDK 21/25
  Android SDK: not used for the OS build; AOSP supplies prebuilts/sdk

Commands:
  ./build.sh check                 offline checks (CI-safe, no device)
  ./build.sh doctor                host tools and resource checks
  ./build.sh verify-pin --network  verify tag, commit and SSH signature
  ./build.sh sync                  sync source into .scratch/grapheneos
  ./build.sh build                 build target-files-package (no device)
  ./build.sh sign --build-number N sign locally with keys outside the repo
  ./build.sh device                explains device-only steps; does not run them
  ./build.sh publish               refused: this project does not publish releases

CI-safe: check, plan, verify-pin (offline), dry-run commands.
Requires a build host: sync, build, sign.
Requires a device: bootloader unlock, flashing, hardware verification. Never
automated here.
EOF
