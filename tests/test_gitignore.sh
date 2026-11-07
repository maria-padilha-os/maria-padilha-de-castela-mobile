#!/usr/bin/env bash
# Validate the ignore boundary for source trees, keys and artifacts.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

assert_ignored() {
    git -C "$ROOT" check-ignore -q -- "$1" || fail "path is not ignored: $1"
}

assert_not_ignored() {
    if git -C "$ROOT" check-ignore -q -- "$1"; then
        fail "path should be tracked, not ignored: $1"
    fi
}

assert_ignored ".scratch/grapheneos/default.xml"
assert_ignored "out/target/product/tegu"
assert_ignored "releases/2026110200/artifact"
assert_ignored "vendor/google/blob.bin"
assert_ignored "keys/tegu/releasekey.pk8"
assert_ignored "private.pem"
assert_ignored "signing.p12"
assert_ignored "device.img"
assert_ignored "artifact.zip"
assert_ignored ".env"
assert_ignored "local.properties"
assert_ignored ".gradle/cache"
pass "source, vendor, key and artifact paths are ignored"

assert_not_ignored "config/release.env"
assert_not_ignored "config/grapheneos-allowed-signers"
assert_not_ignored "docs/BUILD.md"
assert_not_ignored "tests/test_docs.sh"
pass "pin, public key and documentation remain trackable"
