#!/usr/bin/env bash
# Sign a completed build locally using keys that live outside the checkout.
#
# Signing is intentionally offline: this script does not upload, publish, or
# configure an update server. It links <source>/keys to the external key store
# so the upstream GrapheneOS scripts can find the keys without copying them.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

dry_run=0
source_dir="$CASTELA_SOURCE_DIR"
device="$CASTELA_DEFAULT_DEVICE"
key_dir="$CASTELA_SIGNING_KEY_DIR"
build_number="${BUILD_NUMBER:-}"

usage() {
    cat <<'EOF'
Usage: scripts/sign.sh [--dry-run] [--source DIR] [--device NAME]
                       [--build-number N] [--key-dir DIR]

Requires a completed build and the release key set outside this checkout. The
checker reports only file names and permission bits, never key contents. The
signed output stays under the ignored source tree; nothing is published.
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
        --build-number)
            [[ $# -ge 2 ]] || die "--build-number requires a value"
            build_number="$2"
            shift 2
            ;;
        --key-dir)
            [[ $# -ge 2 ]] || die "--key-dir requires a value"
            key_dir="$2"
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

load_device "$device"
source_dir=$(realpath -m -- "$source_dir")
key_dir=$(realpath -m -- "$key_dir")
require_scratch_path "$source_dir"
is_inside_repo "$key_dir" && die "signing keys must live outside the checkout: $key_dir"

if [[ -n "$build_number" ]]; then
    [[ "$build_number" =~ ^[0-9]{10}$ ]] || die "build number must be 10 digits"
elif [[ $dry_run -eq 0 ]]; then
    die "--build-number is required (or set BUILD_NUMBER)"
fi

print_pin
printf '\nSigning device: %s (%s)\n' "$DEVICE" "$DEVICE_NAME"
printf 'Product:        %s\n' "$DEVICE_PRODUCT"
printf 'Key store:      %s\n' "$key_dir"
printf 'Build number:   %s\n' "${build_number:-<required>}"
printf 'Source:         %s\n' "$source_dir"

if [[ $dry_run -eq 1 ]]; then
    cat <<EOF

Would run:
  scripts/check-signing-keys.sh --key-dir "$key_dir" --device "$DEVICE"
  ln -s "$key_dir" "$source_dir/keys"   # only if absent
  cd "$source_dir"
  source build/envsetup.sh
  lunch $DEVICE_PRODUCT
  m otatools-package
  script/finalize.sh
  script/generate-release.sh $DEVICE ${build_number:-<BUILD_NUMBER>}

Output would stay in "$source_dir/releases" (ignored). No upload, publication,
vendor extraction, or device action was performed.
EOF
    exit 0
fi

need_cmd git
[[ -d "$source_dir" ]] || die "source tree missing: $source_dir"
[[ -f "$source_dir/build/envsetup.sh" ]] \
    || die "source tree is not synced: $source_dir/build/envsetup.sh missing"
[[ -f "$source_dir/script/generate-release.sh" ]] \
    || die "source tree is missing GrapheneOS release scripts"
"$ROOT/scripts/verify-pin.sh"
verify_source_pin "$source_dir"

printf '\nChecking signing key presence and permissions (contents are not read)\n'
"$ROOT/scripts/check-signing-keys.sh" --key-dir "$key_dir" --device "$DEVICE"

keys_link="$source_dir/keys"
if [[ -L "$keys_link" ]]; then
    existing_target=$(realpath -m -- "$keys_link")
    [[ "$existing_target" == "$key_dir" ]] \
        || die "source keys symlink points to a different key store"
elif [[ -e "$keys_link" ]]; then
    die "source tree already has a keys path; remove it manually and re-run: $keys_link"
else
    ln -s "$key_dir" "$keys_link"
    printf 'ok linked external key store into the ignored source tree\n'
fi

export OFFICIAL_BUILD=false
export BUILD_NUMBER="$build_number"
export LANG=C
export LC_ALL=C
export TZ=UTC

cd "$source_dir"
printf '\nSourcing build environment\n'
# AOSP's envsetup.sh and release scripts are not nounset-clean.
set +u
# shellcheck disable=SC1091
. build/envsetup.sh
lunch "$DEVICE_PRODUCT"

printf '\nBuilding signing tools\n'
m otatools-package

printf '\nFinalizing local artifacts\n'
script/finalize.sh

printf '\nGenerating signed release locally (no upload)\n'
script/generate-release.sh "$DEVICE" "$build_number"

printf '\nSigned artifacts are under %s/releases/%s and are not published.\n' \
    "$source_dir" "$build_number"
printf 'Do not copy release metadata or artifacts into this repository.\n'
