#!/usr/bin/env bash
# Validate secret scanning and ensure findings do not echo secrets.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

run_capture "$ROOT/scripts/check-secrets.sh"
assert_status 0 "real checkout should contain no obvious secret"
pass "real checkout has no tracked secret"

repo=$(tmpdir)
init_git_repo "$repo"

run_capture "$ROOT/scripts/check-secrets.sh" --root "$repo"
assert_status 0 "clean fixture should pass"
pass "clean fixture passes"

token="ghp_$(printf 'A%.0s' {1..30})"
printf 'token=%s\n' "$token" >"$repo/leak.txt"
git -C "$repo" add leak.txt
git -C "$repo" commit -q -m "add token fixture"

run_capture "$ROOT/scripts/check-secrets.sh" --root "$repo"
assert_status_nonzero "token fixture should fail the scan"
assert_contains "$CAPTURE_OUTPUT" "github-token" "token pattern was not identified"
assert_contains "$CAPTURE_OUTPUT" "leak.txt" "finding did not name the file"
assert_not_contains "$CAPTURE_OUTPUT" "$token" "scanner leaked the token value"
pass "token is detected without printing its value"

git -C "$repo" rm -q leak.txt
printf 'x\n' >"$repo/id_ed25519"
git -C "$repo" add -f id_ed25519
git -C "$repo" commit -q -m "add key filename fixture"

run_capture "$ROOT/scripts/check-secrets.sh" --root "$repo"
assert_status_nonzero "tracked key filename should fail the scan"
assert_contains "$CAPTURE_OUTPUT" "key material filename" "key filename was not identified"
assert_contains "$CAPTURE_OUTPUT" "id_ed25519" "finding did not name the key file"
pass "tracked key material filename is rejected"
