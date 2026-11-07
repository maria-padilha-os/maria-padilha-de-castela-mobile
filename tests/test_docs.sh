#!/usr/bin/env bash
# Validate required documentation coverage.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

for doc in README.md docs/BUILD.md docs/CI.md docs/SIGNING.md manifests/README.md; do
    assert_file "$ROOT/$doc"
    [[ -s "$ROOT/$doc" ]] || fail "document is empty: $doc"
done
pass "required documents exist and are non-empty"

build_doc=$(cat "$ROOT/docs/BUILD.md")
assert_contains "$build_doc" "32 GiB" "BUILD.md omits RAM requirement"
assert_contains "$build_doc" "236 GiB" "BUILD.md omits disk requirement"
assert_contains "$build_doc" "Java" "BUILD.md omits Java requirement"
assert_contains "$build_doc" "Android SDK" "BUILD.md omits Android SDK requirement"
assert_contains "$build_doc" "2026110200" "BUILD.md omits the release tag"
assert_contains "$build_doc" "abed042a17e948a9734e4c3927ce936b5648129f" "BUILD.md omits the commit"
assert_contains "$build_doc" "Reproducibility" "BUILD.md omits reproducibility"
assert_contains "$build_doc" "vendor" "BUILD.md omits the vendor-blob boundary"
pass "build documentation covers disk, RAM, Java, SDK and reproducibility"

ci_doc=$(cat "$ROOT/docs/CI.md")
assert_contains "$ci_doc" "Needs device" "CI.md omits device boundary"
assert_contains "$ci_doc" "verify-pin --network" "CI.md omits network pin verification"
assert_contains "$ci_doc" "never needs a device" "CI.md omits the CI-safe promise"
assert_contains "$ci_doc" "upload artifacts" "CI.md omits the no-artifact rule"
pass "CI documentation separates CI, build host and device steps"

sign_doc=$(cat "$ROOT/docs/SIGNING.md")
assert_contains "$sign_doc" "outside" "SIGNING.md omits key location boundary"
assert_contains "$sign_doc" "never" "SIGNING.md omits the no-print rule"
assert_contains "$sign_doc" "permissions" "SIGNING.md omits permission checks"
assert_contains "$sign_doc" "contents" "SIGNING.md omits content handling"
assert_contains "$sign_doc" "publish" "SIGNING.md omits private-release policy"
pass "signing documentation covers custody and no-print behaviour"

readme=$(cat "$ROOT/README.md")
assert_contains "$readme" "docs/BUILD.md" "README does not link build docs"
assert_contains "$readme" "docs/CI.md" "README does not link CI docs"
assert_contains "$readme" "docs/SIGNING.md" "README does not link signing docs"
assert_contains "$readme" "not official GrapheneOS" "README omits official-project disclaimer"
assert_contains "$readme" "2026110200" "README omits the pinned release"
pass "README links the docs and records the pin"

material=$(cat "$ROOT/manifests/README.md")
assert_contains "$material" "refs/tags/" "manifest docs omit the pinned ref"
assert_contains "$material" "SSH" "manifest docs omit signature verification"
pass "manifest documentation explains the tag pin"
