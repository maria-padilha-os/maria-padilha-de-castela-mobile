#!/usr/bin/env bash
# Refuse proprietary vendor blobs and oversized binary payloads in git.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

root="$ROOT"
max_bytes="${CASTELA_MAX_TRACKED_BYTES:-5242880}"

usage() {
    cat <<'EOF'
Usage: scripts/check-no-vendor-blobs.sh [--root DIR]

Fails when tracked paths look like vendor/firmware payloads, use common blob
extensions, or exceed the tracked-file size limit. Vendor code may be synced
into the ignored source tree; it must never be committed here.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || die "--root requires a value"
            root="$2"
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

root=$(realpath -m -- "$root")
[[ -d "$root" ]] || die "scan root is not a directory: $root"
git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "scan root is not a git work tree: $root"
is_uint "$max_bytes" || die "CASTELA_MAX_TRACKED_BYTES must be an integer"

failures=0
while IFS= read -r -d '' path; do
    case "$path" in
        vendor/* | */vendor/* | proprietary/* | */proprietary/* | firmware/* | */firmware/* | blobs/* | */blobs/* | *.img | *.img.gz | *.bin | *.hex | *.mbn | *.elf)
            printf 'FAIL tracked vendor/blob path: %s\n' "$path" >&2
            failures=$((failures + 1))
            continue
            ;;
    esac

    size=$(stat -c '%s' -- "$root/$path" 2>/dev/null || printf '0')
    if is_uint "$size" && (( size > max_bytes )); then
        printf 'FAIL tracked file exceeds %d bytes: %s (%d bytes)\n' "$max_bytes" "$path" "$size" >&2
        failures=$((failures + 1))
    fi
done < <(git -C "$root" ls-files -z)

if [[ $failures -eq 0 ]]; then
    printf 'ok no tracked vendor blobs or oversized tracked binary\n'
    exit 0
fi

printf 'FAIL vendor blob scan: %d finding(s)\n' "$failures" >&2
exit 1
