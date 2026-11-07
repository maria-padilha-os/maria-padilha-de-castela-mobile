#!/usr/bin/env bash
# Build the unsigned target-files package for the pinned GrapheneOS release.
#
# This step needs a synced tree, 32 GiB+ RAM and ~100 GiB of build space, but
# no device. It never signs, publishes, extracts vendor blobs or flashes.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

dry_run=0
source_dir="$CASTELA_SOURCE_DIR"
device="$CASTELA_DEFAULT_DEVICE"
jobs=""

usage() {
    cat <<'EOF'
Usage: scripts/build.sh [--dry-run] [--source DIR] [--device NAME] [--jobs N]

Builds target-files-package plus the documented vendor boot image targets for
the selected Pixel. The source tree must already be synced at the pinned tag.
No release artifact is published and no device is required.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --source)
            [[ $# -ge 2 ]] || die "--source requires a value"
            source_dir="$2"
            shift 2
            ;;
        --device)
            [[ $# -ge 2 ]] || die "--device requires a value"
            device="$2"
            shift 2
            ;;
        --jobs)
            [[ $# -ge 2 ]] || die "--jobs requires a value"
            jobs="$2"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

[[ -z "$jobs" ]] || { is_uint "$jobs" && (( jobs > 0 )); } || die "jobs must be a positive integer"

load_device "$device"
source_dir=$(realpath -m -- "$source_dir")
require_scratch_path "$source_dir"

targets=()
if [[ "$DEVICE_EXTRA_TARGETS" != "-" && -n "$DEVICE_EXTRA_TARGETS" ]]; then
    read -r -a targets <<<"$DEVICE_EXTRA_TARGETS"
fi
targets+=("target-files-package")

m_args=()
[[ -z "$jobs" ]] || m_args+=("-j$jobs")

print_pin
printf '\nBuilding device: %s (%s)\n' "$DEVICE" "$DEVICE_NAME"
printf 'Product: %s\n' "$DEVICE_PRODUCT"
printf 'Targets: %s\n' "${targets[*]}"
printf 'Source:  %s\n' "$source_dir"

if [[ -n "${BUILD_NUMBER:-}" ]]; then
    [[ "$BUILD_NUMBER" =~ ^[0-9]{10}$ ]] || die "BUILD_NUMBER must be a 10-digit build number"
fi
if [[ -n "${BUILD_DATETIME:-}" ]]; then
    is_uint "$BUILD_DATETIME" || die "BUILD_DATETIME must be an integer Unix timestamp"
fi

if [[ $dry_run -eq 1 ]]; then
    cat <<EOF

Would run:
  cd "$source_dir"
  source build/envsetup.sh
  lunch $DEVICE_PRODUCT
  m ${m_args[*]:-} ${targets[*]}

No build, signing, vendor extraction, or device action was performed.
EOF
    exit 0
fi

need_cmd git
[[ -d "$source_dir" ]] || die "source tree missing: $source_dir"
[[ -f "$source_dir/build/envsetup.sh" ]] \
    || die "source tree is not synced: $source_dir/build/envsetup.sh missing"
"$ROOT/scripts/verify-pin.sh"
verify_source_pin "$source_dir"

export OFFICIAL_BUILD=false
export LANG=C
export LC_ALL=C
export TZ=UTC
[[ -z "${BUILD_NUMBER:-}" ]] || export BUILD_NUMBER
[[ -z "${BUILD_DATETIME:-}" ]] || export BUILD_DATETIME

cd "$source_dir"
printf '\nSourcing build environment\n'
# AOSP's envsetup.sh and make wrapper are not nounset-clean.
set +u
# shellcheck disable=SC1091
. build/envsetup.sh
lunch "$DEVICE_PRODUCT"

printf '\nStarting build (unsigned)\n'
m "${m_args[@]}" "${targets[@]}"

printf '\nBuild complete for %s. Output remains in %s/out and is not published.\n' \
    "$DEVICE" "$source_dir"
printf 'Signing is a separate offline step: ./build.sh sign --build-number N\n'
