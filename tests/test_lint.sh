#!/usr/bin/env bash
# Optional shellcheck lint. Skips cleanly when shellcheck is unavailable.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

if ! command -v shellcheck >/dev/null 2>&1; then
    pass "shellcheck not installed; lint skipped"
    exit 0
fi

mapfile -t scripts < <(
    printf '%s\n' "$ROOT/build.sh"
    find "$ROOT/scripts" "$ROOT/tests" -maxdepth 1 -name '*.sh' -type f -print | sort
)

shellcheck -x -S warning "${scripts[@]}" || fail "shellcheck reported warnings"
pass "shellcheck reported no warnings"
