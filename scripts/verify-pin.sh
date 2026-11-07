#!/usr/bin/env bash
# Verify the pinned GrapheneOS manifest tag.
#
# Default mode is offline and validates the pin records and local manifest.
# --network additionally clones only the small manifest repository, verifies
# the SSH-signed tag with the pinned GrapheneOS allowed-signers file, and
# checks that the tag, commit and AOSP baseline match config/release.env.
#
# No vendor blob is downloaded and no device is touched.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

network=0
allowed_signers="$CONFIG_DIR/grapheneos-allowed-signers"
local_manifest="$ROOT/manifests/castela-local.xml"

usage() {
    cat <<'EOF'
Usage: scripts/verify-pin.sh [--network]

Without --network: validate the recorded tag, tag object, commit, AOSP tag,
device mapping and local manifest shape. This works fully offline.

With --network: also fetch the manifest repository at the exact tag, verify its
SSH signature against the pinned allowed-signers file, and compare the tag and
commit. Only the manifest repository is cloned, into .scratch/.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --network)
            network=1
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            die "unknown option: $1"
            ;;
    esac
done

need_cmd sha256sum
need_cmd python3

[[ "$CASTELA_RELEASE_TAG" =~ ^[0-9]{10}$ ]] \
    || die "release tag is not a 10-digit GrapheneOS tag: $CASTELA_RELEASE_TAG"
[[ "$CASTELA_MANIFEST_TAG_REF" == "refs/tags/$CASTELA_RELEASE_TAG" ]] \
    || die "manifest tag ref does not match release tag"
is_hex40 "$CASTELA_RELEASE_TAG_OBJECT" || die "tag object is not a 40-char lowercase hex id"
is_hex40 "$CASTELA_RELEASE_COMMIT" || die "commit is not a 40-char lowercase hex id"
[[ "$CASTELA_RELEASE_TAG_OBJECT" != "$CASTELA_RELEASE_COMMIT" ]] \
    || die "tag object and commit are identical; expected a signed annotated tag"
[[ "$CASTELA_ANDROID_TAG" =~ ^android-[0-9]+\.[0-9]+\.[0-9]+_r[0-9]+$ ]] \
    || die "invalid AOSP baseline tag: $CASTELA_ANDROID_TAG"
[[ "$CASTELA_MANIFEST_URL" == "https://github.com/GrapheneOS/platform_manifest.git" ]] \
    || die "unexpected manifest URL: $CASTELA_MANIFEST_URL"
[[ -f "$allowed_signers" ]] || die "missing $allowed_signers"

actual_signers_sha=$(sha256sum -- "$allowed_signers" | awk '{print $1}')
[[ "$actual_signers_sha" == "$CASTELA_ALLOWED_SIGNERS_SHA256" ]] \
    || die "allowed-signers file hash does not match the pin"

python3 - "$local_manifest" <<'PY'
import sys
import xml.etree.ElementTree as ET

path = sys.argv[1]
root = ET.parse(path).getroot()
if root.tag != "manifest":
    raise SystemExit(f"local manifest root is not <manifest>: {root.tag}")
PY

load_device "$CASTELA_DEFAULT_DEVICE"
[[ "$DEVICE_PRODUCT" == "$CASTELA_DEFAULT_PRODUCT" ]] \
    || die "default product does not match config/devices.tsv"
[[ "$DEVICE_NAME" == "$CASTELA_DEFAULT_DEVICE_NAME" ]] \
    || die "default device name does not match config/devices.tsv"

printf 'ok pin records: %s tag=%s commit=%s\n' \
    "$CASTELA_BASE_NAME" "$CASTELA_RELEASE_TAG" "$CASTELA_RELEASE_COMMIT"

if [[ $network -eq 0 ]]; then
    printf 'ok offline pin validation (run with --network for signature verification)\n'
    exit 0
fi

need_cmd git
mkdir -p "$ROOT/.scratch"
tmp=$(mktemp -d "$ROOT/.scratch/verify-pin.XXXXXX")
# shellcheck disable=SC2064
trap "remove_scratch_dir '$tmp'" EXIT

printf 'fetching manifest tag %s (manifest repository only)\n' "$CASTELA_RELEASE_TAG"
git init --quiet "$tmp/manifest" || die "could not create temporary manifest repository"
git -C "$tmp/manifest" remote add origin "$CASTELA_MANIFEST_URL"
git -C "$tmp/manifest" fetch --quiet --depth=1 origin \
    "refs/tags/$CASTELA_RELEASE_TAG:refs/tags/$CASTELA_RELEASE_TAG" \
    || die "could not fetch the pinned manifest tag"

git -C "$tmp/manifest" config gpg.ssh.allowedSignersFile "$allowed_signers"

actual_tag_object=$(git -C "$tmp/manifest" rev-parse --verify "$CASTELA_RELEASE_TAG")
actual_commit=$(git -C "$tmp/manifest" rev-parse --verify "$CASTELA_RELEASE_TAG^{commit}")
[[ "$actual_tag_object" == "$CASTELA_RELEASE_TAG_OBJECT" ]] \
    || die "tag object mismatch: expected $CASTELA_RELEASE_TAG_OBJECT, got $actual_tag_object"
[[ "$actual_commit" == "$CASTELA_RELEASE_COMMIT" ]] \
    || die "tag commit mismatch: expected $CASTELA_RELEASE_COMMIT, got $actual_commit"

if ! git -C "$tmp/manifest" verify-tag "$CASTELA_RELEASE_TAG" >/dev/null 2>"$tmp/verify.err"; then
    printf 'ERROR: tag signature verification failed\n' >&2
    sed 's/^/  /' "$tmp/verify.err" >&2
    exit 1
fi

manifest_xml=$(git -C "$tmp/manifest" show "$CASTELA_RELEASE_COMMIT:default.xml")
grep -Eq "<remote name=\"grapheneos\"[^>]*revision=\"refs/tags/$CASTELA_RELEASE_TAG\"" <<<"$manifest_xml" \
    || die "manifest does not pin the GrapheneOS remote to $CASTELA_RELEASE_TAG"
grep -Eq "<default[^>]*revision=\"refs/tags/$CASTELA_ANDROID_TAG\"" <<<"$manifest_xml" \
    || die "manifest does not use the expected AOSP baseline $CASTELA_ANDROID_TAG"

printf 'ok signature verified for %s (%s)\n' "$CASTELA_RELEASE_TAG" "$CASTELA_RELEASE_COMMIT"
printf 'ok manifest pins GrapheneOS %s and AOSP %s\n' "$CASTELA_RELEASE_TAG" "$CASTELA_ANDROID_TAG"
