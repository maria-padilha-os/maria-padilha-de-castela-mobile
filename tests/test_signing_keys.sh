#!/usr/bin/env bash
# Validate key presence checks without ever exposing key contents.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

marker="CASTELA_FAKE_KEY_CONTENT_DO_NOT_PRINT"
store=$(tmpdir)/store
mkdir -p "$store/tegu"
chmod 700 "$store" "$store/tegu"

while IFS= read -r name; do
    [[ -z "${name:-}" ]] && continue
    [[ "$name" == \#* ]] && continue
    printf '%s %s\n' "$marker" "$name" >"$store/tegu/$name"
    chmod 600 "$store/tegu/$name"
done <"$ROOT/config/signing-keys.txt"

run_capture "$ROOT/scripts/check-signing-keys.sh" --key-dir "$store" --device tegu
assert_status 0 "complete external key set should pass"
assert_contains "$CAPTURE_OUTPUT" "contents not read" "checker did not state that contents are unread"
assert_contains "$CAPTURE_OUTPUT" "ok key tegu/releasekey.pk8" "checker did not report the key"
assert_not_contains "$CAPTURE_OUTPUT" "$marker" "checker printed private key contents"
pass "complete key set passes without printing contents"

run_capture "$ROOT/scripts/check-signing-keys.sh" --key-dir "$store/missing" --device tegu --allow-missing
assert_status 0 "missing key store should be a skip with --allow-missing"
assert_contains "$CAPTURE_OUTPUT" "skip signing keys" "missing key store was not reported as a skip"
pass "missing key store is skippable in CI"

run_capture "$ROOT/scripts/check-signing-keys.sh" --key-dir "$ROOT/keys" --device tegu
assert_status_nonzero "inside-repository key store should fail"
assert_contains "$CAPTURE_OUTPUT" "outside the checkout" "inside-repository key store was not rejected"
pass "key store inside the repository is rejected"

chmod 644 "$store/tegu/releasekey.pk8"
run_capture "$ROOT/scripts/check-signing-keys.sh" --key-dir "$store" --device tegu
assert_status_nonzero "group-readable key should fail"
assert_contains "$CAPTURE_OUTPUT" "permissions" "permission failure was not reported"
pass "group-readable private key is rejected"
chmod 600 "$store/tegu/releasekey.pk8"

rm -f "$store/tegu/shared.pk8"
run_capture "$ROOT/scripts/check-signing-keys.sh" --key-dir "$store" --device tegu
assert_status_nonzero "incomplete key set should fail"
assert_contains "$CAPTURE_OUTPUT" "missing key file shared.pk8" "missing key file was not identified"
assert_not_contains "$CAPTURE_OUTPUT" "$marker" "checker printed private key contents on failure"
pass "incomplete key set fails without leaking contents"
