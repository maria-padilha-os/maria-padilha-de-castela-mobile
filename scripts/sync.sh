#!/usr/bin/env bash
# Sync the pinned GrapheneOS source tree into the ignored scratch directory.
#
# This is not a CI step: it needs network access, 90-136 GiB for the source,
# and a build host with enough free disk. It does not extract vendor files,
# run adevtool, flash a device, or write outside this checkout.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

dry_run=0
skip_resources=0
jobs="${CASTELA_JOBS:-8}"
source_dir="$CASTELA_SOURCE_DIR"

usage() {
    cat <<'EOF'
Usage: scripts/sync.sh [--dry-run] [--jobs N] [--source DIR]
                       [--skip-resource-check]

Initialises repo at the signed GrapheneOS tag, installs the local manifest,
verifies the tag and commit, then runs repo sync. Source stays under
.scratch/grapheneos by default and is never committed.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            dry_run=1
            shift
            ;;
        --jobs)
            [[ $# -ge 2 ]] || die "--jobs requires a value"
            jobs="$2"
            shift 2
            ;;
        --source)
            [[ $# -ge 2 ]] || die "--source requires a value"
            source_dir="$2"
            shift 2
            ;;
        --skip-resource-check)
            skip_resources=1
            shift
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

is_uint "$jobs" && (( jobs > 0 )) || die "jobs must be a positive integer"
source_dir=$(realpath -m -- "$source_dir")
require_scratch_path "$source_dir"
[[ "$source_dir" != "$ROOT" ]] || die "source directory cannot be the repository root"

print_pin
printf '\nSource directory: %s\n' "$source_dir"

if [[ $dry_run -eq 1 ]]; then
    cat <<EOF

Would run:
  mkdir -p "$source_dir"
  repo init --no-clone-bundle -u "$CASTELA_MANIFEST_URL" -b "$CASTELA_MANIFEST_TAG_REF"
  install -m 0644 "$ROOT/manifests/castela-local.xml" "$source_dir/.repo/local_manifests/castela.xml"
  git -C "$source_dir/.repo/manifests" verify-tag "$CASTELA_RELEASE_TAG"
  repo sync --no-clone-bundle -j$jobs

No network, vendor extraction, or device action was performed.
EOF
    exit 0
fi

need_cmd repo
need_cmd git
need_cmd install
need_cmd df
"$ROOT/scripts/verify-pin.sh"

if [[ $skip_resources -eq 0 ]]; then
    available=$(disk_available_gib "$ROOT")
    if ! is_uint "$available" || (( available < CASTELA_MIN_DISK_GIB )); then
        die "free disk is ${available:-unknown} GiB; ${CASTELA_MIN_DISK_GIB} GiB required (use --skip-resource-check only if you know the target filesystem)"
    fi
    printf 'ok free disk: %s GiB\n' "$available"
fi

if [[ -e "$source_dir" && ! -d "$source_dir" ]]; then
    die "source path exists and is not a directory: $source_dir"
fi
if [[ -d "$source_dir" && -n "$(ls -A -- "$source_dir" 2>/dev/null)" && ! -d "$source_dir/.repo" ]]; then
    die "source directory is non-empty but is not a repo checkout: $source_dir"
fi
mkdir -p "$source_dir"
cd "$source_dir"

printf '\nInitialising repo at %s\n' "$CASTELA_MANIFEST_TAG_REF"
repo init --no-clone-bundle -u "$CASTELA_MANIFEST_URL" -b "$CASTELA_MANIFEST_TAG_REF"

mkdir -p "$source_dir/.repo/local_manifests"
install -m 0644 "$ROOT/manifests/castela-local.xml" "$source_dir/.repo/local_manifests/castela.xml"

printf '\nVerifying signed manifest tag\n'
git -C "$source_dir/.repo/manifests" config \
    gpg.ssh.allowedSignersFile "$ROOT/config/grapheneos-allowed-signers"
git -C "$source_dir/.repo/manifests" verify-tag "$CASTELA_RELEASE_TAG"

actual_tag_object=$(git -C "$source_dir/.repo/manifests" rev-parse --verify "$CASTELA_RELEASE_TAG")
actual_commit=$(git -C "$source_dir/.repo/manifests" rev-parse --verify "$CASTELA_RELEASE_TAG^{commit}")
[[ "$actual_tag_object" == "$CASTELA_RELEASE_TAG_OBJECT" ]] \
    || die "tag object mismatch: expected $CASTELA_RELEASE_TAG_OBJECT, got $actual_tag_object"
[[ "$actual_commit" == "$CASTELA_RELEASE_COMMIT" ]] \
    || die "tag commit mismatch: expected $CASTELA_RELEASE_COMMIT, got $actual_commit"
printf 'ok manifest tag and commit match the pin\n'

printf '\nSyncing source (this can take a long time)\n'
cd "$source_dir"
repo sync --no-clone-bundle -j"$jobs"

printf '\nSync complete. Next: ./build.sh build --device %s\n' "$CASTELA_DEFAULT_DEVICE"
printf 'No vendor blobs were extracted and no device was touched.\n'
