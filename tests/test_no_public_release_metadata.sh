#!/usr/bin/env bash
# Validate that public release metadata and artifacts are rejected.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

run_capture "$ROOT/scripts/check-public-release-metadata.sh"
assert_status 0 "real checkout should contain no public release metadata"
pass "real checkout has no public release metadata"

repo=$(tmpdir)
init_git_repo "$repo"

run_capture "$ROOT/scripts/check-public-release-metadata.sh" --root "$repo"
assert_status 0 "clean fixture should pass"
pass "clean fixture passes"

dot='.'
bad_url="releases${dot}grapheneos${dot}org"
ota_key="ota""_update"
factory_key="factory""-tegu-2026110200"
{
    printf 'source https://%s/example\n' "$bad_url"
    printf '%s\n' "$ota_key"
    printf '%s\n' "$factory_key"
} >"$repo/leak.txt"
git -C "$repo" add leak.txt
git -C "$repo" commit -q -m "add release metadata fixture"

run_capture "$ROOT/scripts/check-public-release-metadata.sh" --root "$repo"
assert_status_nonzero "public release metadata should fail the scan"
assert_contains "$CAPTURE_OUTPUT" "grapheneos-release-url" "release URL label was not reported"
assert_contains "$CAPTURE_OUTPUT" "ota-update-name" "OTA label was not reported"
assert_contains "$CAPTURE_OUTPUT" "factory-artifact-name" "factory label was not reported"
assert_not_contains "$CAPTURE_OUTPUT" "$bad_url" "scanner printed the release URL"
pass "public release metadata is detected without echoing it"

git -C "$repo" rm -q leak.txt
printf 'not an artifact\n' >"$repo/build-output.zip"
git -C "$repo" add build-output.zip
git -C "$repo" commit -q -m "add artifact fixture"

run_capture "$ROOT/scripts/check-public-release-metadata.sh" --root "$repo"
assert_status_nonzero "tracked release artifact should fail"
assert_contains "$CAPTURE_OUTPUT" "release artifact filename" "artifact filename was not reported"
assert_contains "$CAPTURE_OUTPUT" "build-output.zip" "artifact finding did not name the file"
pass "tracked release artifact filename is rejected"
