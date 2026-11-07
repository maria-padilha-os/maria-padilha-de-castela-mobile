#!/usr/bin/env bash
# Shared test helpers. Sourced by tests/test_*.sh.

set -euo pipefail

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=../scripts/lib.sh
. "$ROOT/scripts/lib.sh"
TEST_TMP_DIRS=()

tmpdir() {
    local dir
    dir=$(mktemp -d "${TMPDIR:-/tmp}/castela-test.XXXXXX")
    TEST_TMP_DIRS+=("$dir")
    printf '%s\n' "$dir"
}

cleanup_tmpdirs() {
    local dir
    for dir in "${TEST_TMP_DIRS[@]:-}"; do
        [[ -n "$dir" && -d "$dir" ]] && rm -rf -- "$dir"
    done
    TEST_TMP_DIRS=()
}

trap cleanup_tmpdirs EXIT

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

pass() {
    printf 'ok %s\n' "$*"
}

assert_eq() {
    local expected="$1" actual="$2" message="${3:-values differ}"
    [[ "$expected" == "$actual" ]] || fail "$message (expected '$expected', got '$actual')"
}

assert_contains() {
    local haystack="$1" needle="$2" message="${3:-missing expected text}"
    case "$haystack" in
        *"$needle"*) ;;
        *) fail "$message: $needle" ;;
    esac
}

assert_not_contains() {
    local haystack="$1" needle="$2" message="${3:-unexpected text}"
    case "$haystack" in
        *"$needle"*) fail "$message: $needle" ;;
        *) ;;
    esac
}

assert_file() {
    [[ -f "$1" ]] || fail "expected file: $1"
}

init_git_repo() {
    local dir="$1"
    git init -q "$dir"
    git -C "$dir" config user.name "Castela Test"
    git -C "$dir" config user.email "test@example.invalid"
    printf 'test fixture\n' >"$dir/README.md"
    git -C "$dir" add README.md
    git -C "$dir" commit -q -m "initial"
}

# Capture combined output and status without tripping errexit.
run_capture() {
    set +e
    CAPTURE_OUTPUT=$("$@" 2>&1)
    CAPTURE_STATUS=$?
    set -e
}

assert_status() {
    local expected="$1" message="${2:-unexpected exit status}"
    [[ "$CAPTURE_STATUS" -eq "$expected" ]] \
        || fail "$message (expected $expected, got $CAPTURE_STATUS; output: $CAPTURE_OUTPUT)"
}

assert_status_nonzero() {
    [[ "$CAPTURE_STATUS" -ne 0 ]] \
        || fail "expected non-zero exit status; output: $CAPTURE_OUTPUT"
}
