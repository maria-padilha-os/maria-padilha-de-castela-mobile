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
  docs/branding/overlay-and-build.md \
  docs/branding/preview.md \
  docs/branding/asset-provenance.md \
  docs/branding/tokens.json \
  docs/security-panel.md \
  docs/local-network-inventory.md \
  docs/pcap-capture-review.md \
  design/padilha_palette.py \
  preview/index.html \
  preview/styles.css \
  preview/palette.js \
  preview/app.js \
  preview/palette-data.js \
  preview/serve.py \
  preview/security/index.html \
  preview/security/security.css \
  preview/security/security.js \
  preview/security/security-panel.js \
  preview/security/network-inventory.js \
  preview/security/pcap-capture.js \
  preview/security/pcap-format.js \
  tools/network_inventory_helper.py \
  tools/pcap_review_helper.py \
  android/design/src/main/res/values/colors.xml \
  android/design/src/main/res/values-night/colors.xml \
  android/overlays/padilha-palette/AndroidManifest.xml \
  android/system/bootanimation/desc.txt \
  assets/wallpapers/padilha-dark-1440x3120.webp \
  assets/fonts/Inter-Regular.woff2 \
  assets/icons/ic_home.svg \
  tests/check_docs.py \
  tests/check_contrast.py \
  tests/test_assets.py \
  tests/test_palette_fallback.py \
  tests/test_light_surface_text.py \
  tests/test_preview.py \
  tests/test_security_panel.py \
  tests/test_network_inventory.py \
  tests/test_pcap_capture.py; do
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

for generator in \
  "python3 tools/export_preview_tokens.py --check" \
  "python3 tools/svg_to_android_vector.py --check" \
  "python3 tools/make_boot_keyframes.py --check"; do
  if $generator >/dev/null; then
    ok "$generator"
  else
    bad "$generator"
  fi
done

if python3 -m unittest discover -s tests -t . -p 'test_*.py' -v; then
  ok "design-system unit tests"
else
  bad "design-system unit tests"
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
  '(^|/)(out|releases|artifacts|keys|signing|secrets|proprietary|vendor)/|\.(img|iso|apk|aab|apks|keystore|jks|p12|pfx|pem|pk8|ota|bin|zip|pcap|pcapng)$' \
  || true)

if [ -n "$tracked_artifacts" ]; then
  bad "tracked build, release, key, or capture artifact"
  printf '%s\n' "$tracked_artifacts"
else
  ok "no tracked build, release, or key artifact"
fi

[ "$fail" -eq 0 ]
