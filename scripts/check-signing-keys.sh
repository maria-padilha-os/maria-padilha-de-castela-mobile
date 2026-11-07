#!/usr/bin/env bash
# Check that release signing keys exist outside the checkout.
#
# This script is intentionally limited to metadata: it checks paths, regular
# files and permission bits. It never reads, hashes, displays or copies key
# material, so it is safe to run without exposing a private key.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

key_dir="${CASTELA_SIGNING_KEY_DIR}"
device="${CASTELA_DEFAULT_DEVICE}"
allow_missing=0
quiet=0

usage() {
    cat <<'EOF'
Usage: scripts/check-signing-keys.sh [--key-dir DIR] [--device NAME]
                                     [--allow-missing] [--quiet]

Exit status is 0 only when the expected key set is present, outside this
repository, and has owner-only permissions. With --allow-missing, an absent
key store is reported as "skip" instead of failing. The script never prints
key contents.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --key-dir)
            [[ $# -ge 2 ]] || die "--key-dir requires a value"
            key_dir="$2"
            shift 2
            ;;
        --device)
            [[ $# -ge 2 ]] || die "--device requires a value"
            device="$2"
            shift 2
            ;;
        --allow-missing)
            allow_missing=1
            shift
            ;;
        --quiet)
            quiet=1
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

[[ -n "$key_dir" ]] || die "signing key directory is empty"
[[ -n "$device" ]] || die "device name is empty"
[[ -r "$SIGNING_KEYS_FILE" ]] || die "missing config/signing-keys.txt"

resolved_key_dir=$(realpath -m -- "$key_dir")
if is_inside_repo "$resolved_key_dir"; then
    die "signing keys must live outside the checkout: $resolved_key_dir"
fi

if [[ ! -e "$resolved_key_dir" ]]; then
    if [[ $allow_missing -eq 1 ]]; then
        [[ $quiet -eq 1 ]] || printf 'skip signing keys: key store not configured (%s)\n' "$resolved_key_dir"
        exit 0
    fi
    die "signing key store missing: $resolved_key_dir"
fi
[[ -d "$resolved_key_dir" ]] || die "signing key path is not a directory: $resolved_key_dir"

device_dir="$resolved_key_dir/$device"
if [[ ! -e "$device_dir" ]]; then
    if [[ $allow_missing -eq 1 ]]; then
        [[ $quiet -eq 1 ]] || printf 'skip signing keys: no key set for device %s\n' "$device"
        exit 0
    fi
    die "signing key set missing for device $device: $device_dir"
fi
[[ -d "$device_dir" ]] || die "signing key set is not a directory: $device_dir"

failures=0
check_dir_mode() {
    local dir="$1" label="$2" mode
    mode=$(stat -c '%a' -- "$dir")
    if (( (8#$mode & 077) != 0 )); then
        printf 'FAIL %s permissions are %s; require owner-only (700 or stricter)\n' "$label" "$mode" >&2
        failures=$((failures + 1))
    fi
}

check_dir_mode "$resolved_key_dir" "key store"
check_dir_mode "$device_dir" "device key set"

checked=0
while IFS= read -r name; do
    [[ -z "${name:-}" ]] && continue
    [[ "$name" == \#* ]] && continue
    path="$device_dir/$name"

    if [[ -L "$path" ]]; then
        target=$(realpath -e -- "$path" 2>/dev/null) || {
            printf 'FAIL %s is a broken symlink\n' "$name" >&2
            failures=$((failures + 1))
            continue
        }
        if is_inside_repo "$target"; then
            printf 'FAIL %s resolves inside the checkout\n' "$name" >&2
            failures=$((failures + 1))
            continue
        fi
    elif [[ ! -e "$path" ]]; then
        printf 'FAIL missing key file %s\n' "$name" >&2
        failures=$((failures + 1))
        continue
    fi

    if [[ ! -f "$path" || ! -r "$path" ]]; then
        printf 'FAIL %s is not a readable regular file\n' "$name" >&2
        failures=$((failures + 1))
        continue
    fi

    # avb_pkmd.bin is a public verification key; everything else is private.
    if [[ "$name" != "avb_pkmd.bin" ]]; then
        mode=$(stat -c '%a' -- "$path")
        if (( (8#$mode & 077) != 0 )); then
            printf 'FAIL %s permissions are %s; require owner-only (600 or stricter)\n' "$name" "$mode" >&2
            failures=$((failures + 1))
            continue
        fi
    fi

    checked=$((checked + 1))
    [[ $quiet -eq 1 ]] || printf 'ok key %s/%s\n' "$device" "$name"
done <"$SIGNING_KEYS_FILE"

if [[ $failures -eq 0 ]]; then
    [[ $quiet -eq 1 ]] || printf 'ok signing keys: %s (%d files checked, contents not read)\n' "$device" "$checked"
    exit 0
fi

printf 'FAIL signing keys: %d problem(s) for device %s\n' "$failures" "$device" >&2
exit 1
