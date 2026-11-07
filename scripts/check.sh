#!/usr/bin/env bash
# Run all offline repository checks. This is the CI entry point.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

failures=0

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

run_check "pinned GrapheneOS release" "$ROOT/scripts/verify-pin.sh"
run_check "CI host tools" "$ROOT/scripts/check-tools.sh" --profile ci
run_check "tracked secrets" "$ROOT/scripts/check-secrets.sh"
run_check "public release metadata" "$ROOT/scripts/check-public-release-metadata.sh"
run_check "vendor blobs" "$ROOT/scripts/check-no-vendor-blobs.sh"
run_check "signing keys (optional in CI)" "$ROOT/scripts/check-signing-keys.sh" --allow-missing

printf '\n== shell syntax ==\n'
syntax_failed=0
while IFS= read -r -d '' script; do
    if ! bash -n "$script"; then
        printf 'FAIL shell syntax: %s\n' "$script" >&2
        syntax_failed=1
    fi
done < <(
    find "$ROOT" \
        \( -path "$ROOT/.git" -o -path "$ROOT/.scratch" -o -path "$ROOT/out" \) -prune -o \
        -name '*.sh' -type f -print0
)
if [[ $syntax_failed -eq 0 ]]; then
    printf 'ok shell syntax\n'
else
    failures=$((failures + 1))
fi

if [[ $failures -eq 0 ]]; then
    printf '\nAll offline checks passed.\n'
    exit 0
fi

printf '\nOffline checks failed: %d group(s).\n' "$failures" >&2
exit 1
