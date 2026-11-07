#!/usr/bin/env bash
# Shared helpers for the Castela Mobile build scaffold.
#
# This file is sourced by the scripts, never executed directly. It deliberately
# avoids privileged commands and only writes below the repository root.

set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG_DIR="$ROOT/config"
RELEASE_FILE="$CONFIG_DIR/release.env"
DEVICES_FILE="$CONFIG_DIR/devices.tsv"
# Used by scripts/check-signing-keys.sh after this file is sourced.
# shellcheck disable=SC2034
SIGNING_KEYS_FILE="$CONFIG_DIR/signing-keys.txt"

# shellcheck source=../config/release.env
. "$RELEASE_FILE"

log() {
    printf '%s\n' "$*"
}

warn() {
    printf 'WARN: %s\n' "$*" >&2
}

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

need_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"
}

is_hex40() {
    [[ "${1:-}" =~ ^[0-9a-f]{40}$ ]]
}

is_uint() {
    [[ "${1:-}" =~ ^[0-9]+$ ]]
}

# True when the resolved path is the checkout root or below it.
is_inside_repo() {
    local resolved
    resolved=$(realpath -m -- "${1:-}")
    case "$resolved" in
        "$ROOT" | "$ROOT"/*) return 0 ;;
        *) return 1 ;;
    esac
}

# Print one tab-separated device row, or fail for an unsupported device.
device_row() {
    local device="${1:-}" row
    [[ -n "$device" ]] || die "device name is empty"
    row=$(awk -F '\t' -v wanted="$device" '
        /^[[:space:]]*#/ || NF == 0 { next }
        $1 == wanted { print; found = 1 }
        END { exit(found ? 0 : 1) }
    ' "$DEVICES_FILE") || die "unsupported device: $device (see config/devices.tsv)"
    printf '%s\n' "$row"
}

# Sets DEVICE, DEVICE_NAME, DEVICE_GENERATION, DEVICE_PRODUCT and
# DEVICE_EXTRA_TARGETS for the selected device.
load_device() {
    local row
    row=$(device_row "${1:-}")
    # These are consumed by callers after load_device returns.
    # shellcheck disable=SC2034
    IFS=$'\t' read -r DEVICE DEVICE_NAME DEVICE_GENERATION DEVICE_PRODUCT DEVICE_EXTRA_TARGETS <<<"$row"
    [[ -n "$DEVICE" && -n "$DEVICE_PRODUCT" ]] || die "malformed device row for ${1:-}"
}

# Only remove a directory that looks like one of our scratch directories.
remove_scratch_dir() {
    local target
    [[ $# -eq 1 ]] || die "remove_scratch_dir expects one path"
    target=$(realpath -m -- "$1")
    case "$target" in
        "$ROOT"/.scratch/*) rm -rf -- "$target" ;;
        *) die "refusing to remove path outside .scratch: $target" ;;
    esac
}

print_pin() {
    cat <<EOF
Base:        $CASTELA_BASE_NAME $CASTELA_BASE_BRANCH
Release tag: $CASTELA_RELEASE_TAG
Tag object:  $CASTELA_RELEASE_TAG_OBJECT
Commit:      $CASTELA_RELEASE_COMMIT
AOSP tag:    $CASTELA_ANDROID_TAG
Manifest:    $CASTELA_MANIFEST_URL
Device:      $CASTELA_DEFAULT_DEVICE ($CASTELA_DEFAULT_DEVICE_NAME)
Product:     $CASTELA_DEFAULT_PRODUCT
EOF
}

memory_gib() {
    awk '/^MemTotal:/ { printf "%d\n", $2 / 1024 / 1024; exit }' /proc/meminfo
}

disk_available_gib() {
    df -Pk -- "${1:-$ROOT}" | awk 'NR == 2 { printf "%d\n", $4 / 1024 / 1024; exit }'
}

# Fail unless PATH_DIR is inside the checkout. Builds are not allowed to write
# outside this worktree, so every generated path is checked first.
require_inside_repo() {
    local path
    path=$(realpath -m -- "${1:-}")
    is_inside_repo "$path" || die "path is outside this checkout: $path"
}

# Source and signed artifacts must stay in the ignored scratch tree so a build
# can never dirty tracked paths.
require_scratch_path() {
    local path
    path=$(realpath -m -- "${1:-}")
    case "$path" in
        "$ROOT"/.scratch/*) ;;
        *) die "path is outside this checkout or not under .scratch: $path" ;;
    esac
}

# Verify that a synced tree's repo manifest still matches the pin and that the
# signed tag is intact. This is offline and uses the vendored public key.
verify_source_pin() {
    local source_dir manifests_dir actual_tag actual_commit
    source_dir=$(realpath -m -- "${1:-}")
    manifests_dir="$source_dir/.repo/manifests"
    [[ -d "$manifests_dir" ]] \
        || die "source tree has no repo manifest; run ./build.sh sync first: $source_dir"

    git -C "$manifests_dir" config \
        gpg.ssh.allowedSignersFile "$ROOT/config/grapheneos-allowed-signers"
    git -C "$manifests_dir" verify-tag "$CASTELA_RELEASE_TAG" >/dev/null 2>&1 \
        || die "source manifest tag signature is missing or invalid"

    actual_tag=$(git -C "$manifests_dir" rev-parse --verify "$CASTELA_RELEASE_TAG")
    actual_commit=$(git -C "$manifests_dir" rev-parse --verify "$CASTELA_RELEASE_TAG^{commit}")
    [[ "$actual_tag" == "$CASTELA_RELEASE_TAG_OBJECT" ]] \
        || die "source tag object mismatch: expected $CASTELA_RELEASE_TAG_OBJECT, got $actual_tag"
    [[ "$actual_commit" == "$CASTELA_RELEASE_COMMIT" ]] \
        || die "source commit mismatch: expected $CASTELA_RELEASE_COMMIT, got $actual_commit"
}
