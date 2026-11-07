#!/usr/bin/env bash
# Validate that vendor blobs and oversized tracked files are rejected.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

run_capture "$ROOT/scripts/check-no-vendor-blobs.sh"
assert_status 0 "real checkout should contain no vendor blob"
pass "real checkout has no tracked vendor blob"

repo=$(tmpdir)
init_git_repo "$repo"

run_capture "$ROOT/scripts/check-no-vendor-blobs.sh" --root "$repo"
assert_status 0 "clean fixture should pass"
pass "clean fixture passes"

mkdir -p "$repo/vendor/google"
printf 'placeholder\n' >"$repo/vendor/google/blob.dat"
git -C "$repo" add vendor/google/blob.dat
git -C "$repo" commit -q -m "add vendor path fixture"

run_capture "$ROOT/scripts/check-no-vendor-blobs.sh" --root "$repo"
assert_status_nonzero "vendor path should fail"
assert_contains "$CAPTURE_OUTPUT" "vendor/blob path" "vendor path was not reported"
assert_contains "$CAPTURE_OUTPUT" "vendor/google/blob.dat" "finding did not name the file"
pass "tracked vendor path is rejected"

git -C "$repo" rm -q vendor/google/blob.dat
printf 'placeholder\n' >"$repo/device.img"
git -C "$repo" add device.img
git -C "$repo" commit -q -m "add image fixture"

run_capture "$ROOT/scripts/check-no-vendor-blobs.sh" --root "$repo"
assert_status_nonzero "tracked image should fail"
assert_contains "$CAPTURE_OUTPUT" "device.img" "image filename was not reported"
pass "tracked image extension is rejected"

git -C "$repo" rm -q device.img
truncate -s 6000000 "$repo/large.dat"
git -C "$repo" add large.dat
git -C "$repo" commit -q -m "add oversized fixture"

run_capture "$ROOT/scripts/check-no-vendor-blobs.sh" --root "$repo"
assert_status_nonzero "oversized tracked file should fail"
assert_contains "$CAPTURE_OUTPUT" "exceeds" "oversized file was not reported"
pass "oversized tracked file is rejected"
