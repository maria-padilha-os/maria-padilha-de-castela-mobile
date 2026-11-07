#!/usr/bin/env bash
# Validate the entry point, dry runs, and refused commands.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

run_capture "$ROOT/build.sh" plan
assert_status 0 "plan should succeed"
assert_contains "$CAPTURE_OUTPUT" "$CASTELA_RELEASE_TAG" "plan omits the pinned tag"
assert_contains "$CAPTURE_OUTPUT" "$CASTELA_RELEASE_COMMIT" "plan omits the pinned commit"
assert_contains "$CAPTURE_OUTPUT" "Java" "plan omits Java requirements"
assert_contains "$CAPTURE_OUTPUT" "Android SDK" "plan omits Android SDK requirements"
assert_contains "$CAPTURE_OUTPUT" "CI-safe" "plan omits the CI/device split"
pass "plan reports the pin and requirements"

run_capture "$ROOT/build.sh" check
assert_status 0 "offline check command should succeed"
assert_contains "$CAPTURE_OUTPUT" "All offline checks passed" "check did not report success"
pass "offline check command succeeds"

run_capture "$ROOT/build.sh" sync --dry-run
assert_status 0 "sync dry run should succeed without repo or network"
assert_contains "$CAPTURE_OUTPUT" "repo init" "sync dry run omits repo init"
assert_contains "$CAPTURE_OUTPUT" "refs/tags/$CASTELA_RELEASE_TAG" "sync dry run omits the pinned tag"
assert_contains "$CAPTURE_OUTPUT" "No network" "sync dry run does not state that nothing ran"
pass "sync dry run is offline and non-mutating"

run_capture "$ROOT/build.sh" build --device tegu --dry-run
assert_status 0 "build dry run should succeed without source"
assert_contains "$CAPTURE_OUTPUT" "lunch tegu-cur-user" "build dry run omits lunch target"
assert_contains "$CAPTURE_OUTPUT" "target-files-package" "build dry run omits the make target"
assert_contains "$CAPTURE_OUTPUT" "vendorbootimage" "build dry run omits vendor boot targets"
pass "build dry run prints the pinned target commands"

run_capture "$ROOT/build.sh" sign --build-number 2026110200 --dry-run
assert_status 0 "sign dry run should succeed without keys"
assert_contains "$CAPTURE_OUTPUT" "check-signing-keys.sh" "sign dry run omits the key check"
assert_contains "$CAPTURE_OUTPUT" "generate-release.sh" "sign dry run omits release generation"
assert_contains "$CAPTURE_OUTPUT" "No upload" "sign dry run does not state that nothing was published"
pass "sign dry run is local-only"

run_capture "$ROOT/build.sh" device
assert_status 2 "device command must refuse to run"
assert_contains "$CAPTURE_OUTPUT" "physical device" "device refusal is unclear"
assert_contains "$CAPTURE_OUTPUT" "not automated" "device refusal does not state the boundary"
pass "device command refuses and explains the split"

run_capture "$ROOT/build.sh" publish
assert_status 2 "publish command must refuse"
assert_contains "$CAPTURE_OUTPUT" "Refusing to publish" "publish refusal is unclear"
pass "publish command refuses"

run_capture "$ROOT/build.sh" build --device not-a-device --dry-run
assert_status_nonzero "unsupported device should fail"
assert_contains "$CAPTURE_OUTPUT" "unsupported device" "unsupported device was not reported"
pass "unsupported device is rejected"

run_capture "$ROOT/build.sh" sync --source /tmp/outside-castela --dry-run
assert_status_nonzero "source outside the checkout should fail"
assert_contains "$CAPTURE_OUTPUT" "outside this checkout" "outside path was not rejected"
pass "writes outside the checkout are rejected"

run_capture "$ROOT/build.sh" unknown-command
assert_status 2 "unknown command should exit 2"
assert_contains "$CAPTURE_OUTPUT" "Unknown command" "unknown command was not reported"
pass "unknown command is rejected"
