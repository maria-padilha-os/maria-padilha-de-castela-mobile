#!/usr/bin/env bash
# Check the host before syncing or building. Never installs anything.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

no_resources=0
failures=0

usage() {
    cat <<'EOF'
Usage: scripts/doctor.sh [--no-resources]

Runs the offline checks and verifies build tools, architecture, RAM and free
disk against docs/BUILD.md. --no-resources skips the RAM/disk thresholds and
is useful on a small CI runner. The script never installs packages or uses a
privileged command.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --no-resources)
            no_resources=1
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

run_check() {
    local label="$1"
    shift
    printf '\n== %s ==\n' "$label"
    if "$@"; then
        return 0
    fi
    printf 'FAIL check: %s\n' "$label" >&2
    failures=$((failures + 1))
    return 0
}

run_check "offline repository checks" "$ROOT/scripts/check.sh"
run_check "build host tools" "$ROOT/scripts/check-tools.sh" --profile build
run_check "signing keys (optional until signing)" "$ROOT/scripts/check-signing-keys.sh" --allow-missing

printf '\n== host platform ==\n'
arch=$(uname -m)
if [[ "$arch" == "x86_64" ]]; then
    printf 'ok architecture: %s\n' "$arch"
else
    printf 'FAIL architecture: %s (GrapheneOS builds require x86_64)\n' "$arch" >&2
    failures=$((failures + 1))
fi

if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf 'info host OS: %s\n' "${PRETTY_NAME:-unknown}"
    case " ${ID:-} ${ID_LIKE:-} " in
        *ubuntu* | *debian* | *arch*) ;;
        *)
            printf 'WARN unsupported host OS for reproducible builds: %s\n' "${PRETTY_NAME:-unknown}" >&2
            ;;
    esac
fi

printf 'info host Java: not required for the OS build (AOSP prebuilts JDK 21/25)\n'
printf 'info Android SDK: not required for the OS build (AOSP prebuilts/sdk)\n'

if [[ $no_resources -eq 0 ]]; then
    printf '\n== host resources ==\n'
    ram=$(memory_gib)
    if is_uint "$ram" && (( ram >= CASTELA_MIN_RAM_GIB )); then
        printf 'ok RAM: %s GiB (minimum %s GiB)\n' "$ram" "$CASTELA_MIN_RAM_GIB"
    else
        printf 'FAIL RAM: %s GiB available, %s GiB required\n' "${ram:-unknown}" "$CASTELA_MIN_RAM_GIB" >&2
        failures=$((failures + 1))
    fi

    available=$(disk_available_gib "$ROOT")
    if is_uint "$available" && (( available >= CASTELA_MIN_DISK_GIB )); then
        printf 'ok free disk: %s GiB (minimum %s GiB, recommended %s GiB)\n' \
            "$available" "$CASTELA_MIN_DISK_GIB" "$CASTELA_RECOMMENDED_DISK_GIB"
    else
        printf 'FAIL free disk: %s GiB available, %s GiB required\n' \
            "${available:-unknown}" "$CASTELA_MIN_DISK_GIB" >&2
        failures=$((failures + 1))
    fi
fi

if [[ $failures -eq 0 ]]; then
    printf '\nHost is ready for sync/build.\n'
    exit 0
fi

printf '\nHost check failed: %d group(s). Do not continue until resolved.\n' "$failures" >&2
exit 1
