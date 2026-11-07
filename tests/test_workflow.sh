#!/usr/bin/env bash
# Validate CI workflows stay device-free, secret-free and artifact-free.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ci="$ROOT/.github/workflows/ci.yml"
pin="$ROOT/.github/workflows/pin-verify.yml"
assert_file "$ci"
assert_file "$pin"

ci_text=$(cat "$ci")
assert_contains "$ci_text" "./tests/all.sh" "CI does not run the test suite"
assert_contains "$ci_text" "contents: read" "CI does not use a read-only token"
assert_contains "$ci_text" "permissions:" "CI omits permissions"
assert_not_contains "$ci_text" "upload-artifact" "CI uploads artifacts"
assert_not_contains "$ci_text" "secrets." "CI references secrets"
assert_not_contains "$ci_text" "pull_request_target" "CI uses an unsafe PR trigger"
assert_not_contains "$ci_text" "adb" "CI references adb"
assert_not_contains "$ci_text" "fastboot" "CI references fastboot"
assert_not_contains "$ci_text" "sudo" "CI uses sudo"
grep -Eq 'uses: actions/checkout@[0-9a-f]{40}' "$ci" \
    || fail "CI does not pin actions/checkout by commit"
pass "CI workflow is offline, read-only and artifact-free"

pin_text=$(cat "$pin")
assert_contains "$pin_text" "./scripts/verify-pin.sh --network" "pin workflow does not verify the tag"
assert_contains "$pin_text" "schedule:" "pin workflow has no schedule"
assert_contains "$pin_text" "workflow_dispatch:" "pin workflow cannot be run manually"
assert_contains "$pin_text" "contents: read" "pin workflow does not use a read-only token"
assert_not_contains "$pin_text" "upload-artifact" "pin workflow uploads artifacts"
assert_not_contains "$pin_text" "secrets." "pin workflow references secrets"
grep -Eq 'uses: actions/checkout@[0-9a-f]{40}' "$pin" \
    || fail "pin workflow does not pin actions/checkout by commit"
pass "scheduled pin verification is read-only and manifest-only"
