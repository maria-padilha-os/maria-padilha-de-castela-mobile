#!/usr/bin/env bash
# Refuse public release metadata and release artifacts in the repository.
#
# The project is private-release-only. This check catches upstream download
# URLs, update-channel metadata, signed factory/OTA names, and tracked build
# artifacts. It prints file and line references, not the matching content.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

root="$ROOT"

usage() {
    cat <<'EOF'
Usage: scripts/check-public-release-metadata.sh [--root DIR]

Fails when tracked files contain public release download URLs, OTA/factory
artifact names, update-channel metadata, or tracked build artifacts.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || die "--root requires a value"
            root="$2"
            shift 2
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

root=$(realpath -m -- "$root")
[[ -d "$root" ]] || die "scan root is not a directory: $root"
git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "scan root is not a git work tree: $root"

failures=0

patterns=(
    "grapheneos-release-url|releases\\.grapheneos\\.org"
    "ota-update-name|ota_update"
    "factory-artifact-name|factory-[a-z0-9]+-[0-9]{8,}"
    "install-artifact-name|install-[a-z0-9]+-[0-9]{8,}"
    "update-signature-name|\\.zip\\.sig"
    "release-channel-metadata|(^|[^A-Za-z0-9_])(DEVICE)-(stable|beta|testing)([^A-Za-z0-9_]|$)"
    "public-download-url|https?://[^[:space:]]*/(releases?|downloads?)/[^[:space:]]*\\.(zip|img|sig)"
    "public-release-path|(^|/)releases/[0-9]{8,}/"
)

for entry in "${patterns[@]}"; do
    label="${entry%%|*}"
    pattern="${entry#*|}"
    if matches=$(git -C "$root" grep -n -I -E -e "$pattern" -- . 2>/dev/null); then
        while IFS=: read -r file line _rest; do
            [ "$file" = "scripts/check-public-release-metadata.sh" ] && continue
            printf 'FAIL public release metadata: %s:%s (%s)\n' "$file" "$line" "$label" >&2
            failures=$((failures + 1))
        done <<<"$matches"
    else
        status=$?
        [[ $status -eq 1 ]] || die "git grep failed while scanning $label (status $status)"
    fi
done

while IFS= read -r -d '' path; do
    case "$path" in
        releases/* | *.zip | *.img | *.sig | *.ota | *.tar | *.tar.gz | *.pkg.tar.zst)
            printf 'FAIL tracked release artifact filename: %s\n' "$path" >&2
            failures=$((failures + 1))
            ;;
    esac
done < <(git -C "$root" ls-files -z)

if [[ $failures -eq 0 ]]; then
    printf 'ok no public release metadata or artifacts\n'
    exit 0
fi

printf 'FAIL public release metadata scan: %d finding(s)\n' "$failures" >&2
exit 1
