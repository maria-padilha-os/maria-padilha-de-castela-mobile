#!/usr/bin/env bash
# Repository test suite. Runs without a device, network, signing keys or build.

set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

failures=0

printf '== shell syntax ==\n'
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
    printf 'ok all shell scripts parse\n'
else
    failures=$((failures + 1))
fi

printf '\n== test scripts ==\n'
for test in "$ROOT"/tests/test_*.sh; do
    name=$(basename "$test")
    printf '\n-- %s --\n' "$name"
    if bash "$test"; then
        printf 'PASS %s\n' "$name"
    else
        printf 'FAIL %s\n' "$name" >&2
        failures=$((failures + 1))
    fi
done

if [[ $failures -eq 0 ]]; then
    printf '\nAll tests passed.\n'
    exit 0
fi

printf '\nTests failed: %d group(s).\n' "$failures" >&2
exit 1
