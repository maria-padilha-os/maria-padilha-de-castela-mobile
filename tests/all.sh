#!/usr/bin/env bash
set -euo pipefail

root=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
cd "$root"

fail=0
ok() { echo "ok $*"; }
bad() { echo "FAIL $*"; fail=1; }

require_file() {
  local path=$1
  if [ -s "$path" ]; then
    ok "$path"
  else
    bad "$path missing or empty"
  fi
}

for path in \
  README.md \
  docs/adr/0001-grapheneos-base-device-support-and-padilha-branding.md \
  docs/legal/grapheneos-aosp-attribution.md \
  docs/branding/padilha-look-and-feel.md \
  docs/branding/tokens.json \
  tests/check_docs.py \
  tests/check_contrast.py; do
  require_file "$path"
done

if python3 tests/check_docs.py; then
  ok "documentation checks"
else
  bad "documentation checks"
fi

if python3 tests/check_contrast.py; then
  ok "contrast checks"
else
  bad "contrast checks"
fi

scan_file=$(mktemp)
trap 'rm -f "$scan_file"' EXIT

scan_status=0
grep -RInE \
  'sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY' \
  --exclude-dir=.git \
  --exclude-dir=.git-local \
  --exclude-dir=.scratch \
  --exclude-dir=out \
  --exclude-dir=build \
  --exclude-dir=.gradle \
  --exclude='*.png' \
  --exclude='*.jpg' \
  --exclude='*.jpeg' \
  --exclude='*.webp' \
  --exclude='*.gif' \
  . >"$scan_file" 2>/dev/null || scan_status=$?

if [ "$scan_status" -eq 0 ]; then
  bad "possible tracked secret"
  cat "$scan_file"
elif [ "$scan_status" -eq 1 ]; then
  ok "no obvious tracked secret"
else
  bad "secret scan could not complete"
fi

tracked_artifacts=$(git ls-files | grep -E \
  '(^|/)(out|releases|artifacts|keys|signing|secrets|proprietary|vendor)/|\.(img|iso|apk|aab|apks|keystore|jks|p12|pfx|pem|pk8|ota|bin|zip)$' \
  || true)

if [ -n "$tracked_artifacts" ]; then
  bad "tracked build, release, or key artifact"
  printf '%s\n' "$tracked_artifacts"
else
  ok "no tracked build, release, or key artifact"
fi

[ "$fail" -eq 0 ]
