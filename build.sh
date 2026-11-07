#!/usr/bin/env bash
# Castela Mobile private-build entry point.
#
# This wrapper never runs a privileged command, never flashes a device, and
# never publishes an artifact. Device work and publication are deliberately
# not implemented.

set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
    shift
fi

usage() {
    cat <<'EOF'
Usage: ./build.sh <command> [options]

Commands:
  plan          Print the pinned base, requirements and command split.
  check         Run offline checks (CI-safe, no device).
  doctor        Check host tools, RAM and disk.
  verify-pin    Validate the pin offline; add --network for signature check.
  sync          Sync the pinned source into .scratch/grapheneos.
  build         Build unsigned target-files-package (no device).
  sign          Sign locally with keys outside the repository.
  test          Run the repository test suite.
  device        Explain device-only steps (does not run them).
  publish       Refused: private builds are never published.
  help          Show this text.

Common options are passed through, for example:
  ./build.sh verify-pin --network
  ./build.sh sync --dry-run
  ./build.sh build --device tegu --dry-run
  ./build.sh sign --build-number 2026110200 --dry-run

CI can run: plan, check, test, verify-pin (offline), and all --dry-run forms.
Requires a build host: sync, build, sign.
Requires a device: bootloader unlock, flashing, hardware verification.
EOF
}

case "$cmd" in
    plan)
        exec "$ROOT/scripts/plan.sh" "$@"
        ;;
    check)
        exec "$ROOT/scripts/check.sh" "$@"
        ;;
    doctor)
        exec "$ROOT/scripts/doctor.sh" "$@"
        ;;
    verify-pin)
        exec "$ROOT/scripts/verify-pin.sh" "$@"
        ;;
    sync)
        exec "$ROOT/scripts/sync.sh" "$@"
        ;;
    build)
        exec "$ROOT/scripts/build.sh" "$@"
        ;;
    sign)
        exec "$ROOT/scripts/sign.sh" "$@"
        ;;
    test)
        exec "$ROOT/tests/all.sh" "$@"
        ;;
    device)
        cat >&2 <<'EOF'
Device operations require a physical device and are intentionally not automated
by this scaffold: bootloader unlock, factory-image flashing, OTA sideloading and
hardware verification. No flash command is provided, no adb/fastboot wrapper is
included, and nothing here may be run in CI. Follow the GrapheneOS install/usage
documentation manually and keep the device offline until the signed build is
verified.
EOF
        exit 2
        ;;
    publish | release | upload)
        cat >&2 <<'EOF'
Refusing to publish: this project keeps release builds private. There is no
upload command, update server configuration, or public release metadata in
this repository. Signed artifacts stay local and ignored by git.
EOF
        exit 2
        ;;
    help | -h | --help)
        usage
        ;;
    *)
        printf 'Unknown command: %s\n\n' "$cmd" >&2
        usage >&2
        exit 2
        ;;
esac
