#!/usr/bin/env bash
# Validate the tool checker and its failure behaviour.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

run_capture "$ROOT/scripts/check-tools.sh" --profile ci
assert_status 0 "CI tool profile should pass on this host"
assert_contains "$CAPTURE_OUTPUT" "ok profile ci" "CI tool profile did not report success"
pass "CI tool profile passes"

run_capture "$ROOT/scripts/check-tools.sh" --profile build --list
assert_status 0 "tool list should not fail"
assert_contains "$CAPTURE_OUTPUT" "repo" "build profile does not list repo"
assert_contains "$CAPTURE_OUTPUT" "ssh-keygen" "build profile does not list ssh-keygen"
assert_contains "$CAPTURE_OUTPUT" "openssl" "build profile does not list openssl"
pass "build tool list includes repo and signing dependencies"

run_capture "$ROOT/scripts/check-tools.sh" --profile ci --json
assert_status 0 "JSON tool check should pass"
printf '%s\n' "$CAPTURE_OUTPUT" | python3 -c '
import json
import sys

data = json.load(sys.stdin)
assert data["profile"] == "ci"
assert data["ok"] is True
assert data["missing"] == []
' || fail "tool JSON output is not valid or does not report no missing tools"
pass "tool JSON output is valid"

fake_bin=$(tmpdir)
mkdir -p "$fake_bin/bin"
ln -s "$(command -v dirname)" "$fake_bin/bin/dirname"
ln -s "$(command -v awk)" "$fake_bin/bin/awk"

set +e
missing_output=$(PATH="$fake_bin/bin" /bin/bash "$ROOT/scripts/check-tools.sh" --profile ci 2>&1)
missing_status=$?
set -e
[[ $missing_status -ne 0 ]] || fail "tool checker should fail when git is absent"
assert_contains "$missing_output" "missing tool git" "missing tool was not reported"
pass "missing tools are reported and fail the check"

run_capture "$ROOT/scripts/check-tools.sh" --profile nonexistent
assert_status_nonzero "invalid profile should fail"
pass "invalid tool profile is rejected"
