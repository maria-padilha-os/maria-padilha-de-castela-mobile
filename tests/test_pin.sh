#!/usr/bin/env bash
# Validate the pinned GrapheneOS release records.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

# shellcheck source=../config/release.env
. "$ROOT/config/release.env"

[[ "$CASTELA_RELEASE_TAG" =~ ^[0-9]{10}$ ]] || fail "release tag is not a 10-digit GrapheneOS tag"
is_hex40 "$CASTELA_RELEASE_TAG_OBJECT" || fail "tag object is not 40-char hex"
is_hex40 "$CASTELA_RELEASE_COMMIT" || fail "commit is not 40-char hex"
[[ "$CASTELA_RELEASE_TAG_OBJECT" != "$CASTELA_RELEASE_COMMIT" ]] \
    || fail "tag object and commit should differ for an annotated tag"
[[ "$CASTELA_MANIFEST_TAG_REF" == "refs/tags/$CASTELA_RELEASE_TAG" ]] \
    || fail "manifest tag ref does not match release tag"
[[ "$CASTELA_MANIFEST_URL" == "https://github.com/GrapheneOS/platform_manifest.git" ]] \
    || fail "unexpected manifest URL"
[[ "$CASTELA_ANDROID_TAG" =~ ^android-[0-9]+\.[0-9]+\.[0-9]+_r[0-9]+$ ]] \
    || fail "invalid AOSP baseline tag"
[[ "$CASTELA_BASE_BRANCH" == "17" ]] || fail "unexpected GrapheneOS branch"
pass "release fields have the expected shape"

actual_signers_sha=$(sha256sum -- "$ROOT/config/grapheneos-allowed-signers" | awk '{print $1}')
assert_eq "$CASTELA_ALLOWED_SIGNERS_SHA256" "$actual_signers_sha" \
    "allowed-signers hash does not match the pin"

signer_lines=$(grep -vc '^[[:space:]]*$' "$ROOT/config/grapheneos-allowed-signers")
assert_eq "1" "$signer_lines" "expected exactly one public allowed signer"
grep -q '^contact@grapheneos.org ssh-ed25519 ' "$ROOT/config/grapheneos-allowed-signers" \
    || fail "allowed signers file does not contain the expected public key"
pass "public allowed-signers key is pinned by hash"

python3 - "$ROOT/manifests/castela-local.xml" <<'PY'
import sys
import xml.etree.ElementTree as ET

root = ET.parse(sys.argv[1]).getroot()
if root.tag != "manifest":
    raise SystemExit("local manifest root is not <manifest>")
PY
pass "local manifest is well-formed XML"

row=$(device_row "$CASTELA_DEFAULT_DEVICE")
IFS=$'\t' read -r device name generation product extra_targets <<<"$row"
assert_eq "$CASTELA_DEFAULT_DEVICE" "$device" "default device mismatch"
assert_eq "$CASTELA_DEFAULT_DEVICE_NAME" "$name" "default device name mismatch"
assert_eq "$CASTELA_DEFAULT_PRODUCT" "$product" "default product mismatch"
[[ "$generation" =~ ^[0-9]+$ ]] || fail "device generation is not numeric"
[[ -n "$extra_targets" ]] || fail "device extra targets are empty"
pass "default device maps consistently to devices.tsv"

for doc in "$ROOT/README.md" "$ROOT/docs/BUILD.md" "$ROOT/manifests/README.md"; do
    assert_contains "$(cat "$doc")" "$CASTELA_RELEASE_TAG" "doc does not mention pinned tag: $doc"
done
assert_contains "$(cat "$ROOT/docs/BUILD.md")" "$CASTELA_RELEASE_COMMIT" \
    "BUILD.md does not mention pinned commit"
assert_contains "$(cat "$ROOT/docs/BUILD.md")" "$CASTELA_RELEASE_TAG_OBJECT" \
    "BUILD.md does not mention tag object"
pass "documentation records the pin"

if grep -q 'refs/heads/' "$ROOT/config/release.env"; then
    fail "release.env must not pin a development branch"
fi
pass "pin does not follow a development branch"

# Offline command must not need the network.
run_capture "$ROOT/scripts/verify-pin.sh"
assert_status 0 "offline pin verification failed"
assert_contains "$CAPTURE_OUTPUT" "offline pin validation" "offline verify output is unclear"

pass "offline pin verification succeeds"
