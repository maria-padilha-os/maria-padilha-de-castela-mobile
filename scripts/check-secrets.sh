#!/usr/bin/env bash
# Scan tracked text for obvious secrets and key material.
#
# Findings identify only file and line number. The matched text is never
# printed, so a scan cannot leak a credential into CI logs.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

root="$ROOT"

usage() {
    cat <<'EOF'
Usage: scripts/check-secrets.sh [--root DIR]

Scans git-tracked files under DIR (default: this checkout) for private keys,
common API tokens, keystore passwords, and tracked key-store filenames. It
prints file and line numbers only, never the matching content.
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
    "private-key|-----BEGIN ([A-Z0-9]+ )?PRIVATE KEY-----"
    "ssh-private-key|BEGIN OPENSSH PRIVATE KEY"
    "github-token|gh[pousr]_[A-Za-z0-9]{20,}"
    "gitlab-token|glpat-[A-Za-z0-9_-]{20,}"
    "openai-key|sk-[A-Za-z0-9]{20,}"
    "aws-access-key|AKIA[0-9A-Z]{16}"
    "google-api-key|AIza[0-9A-Za-z_-]{35}"
    "keystore-password|(store|key)Password[[:space:]]*=[[:space:]]*[^[:space:]]+"
    "signing-password|(SIGNING|KEYSTORE)_PASSWORD[[:space:]]*="
    "age-secret-key|AGE-SECRET-KEY-1[0-9A-Z]{20,}"
)

for entry in "${patterns[@]}"; do
    label="${entry%%|*}"
    pattern="${entry#*|}"
    if matches=$(git -C "$root" grep -n -I -E -e "$pattern" -- . 2>/dev/null); then
        while IFS=: read -r file line _rest; do
            printf 'FAIL possible secret: %s:%s (%s)\n' "$file" "$line" "$label" >&2
            failures=$((failures + 1))
        done <<<"$matches"
    else
        status=$?
        [[ $status -eq 1 ]] || die "git grep failed while scanning $label (status $status)"
    fi
done

while IFS= read -r -d '' path; do
    case "$path" in
        .env | */.env | keys/* | */keys/* | *.pk8 | *.jks | *.keystore | *.p12 | *.pfx | id_ed25519 | *.pem)
            printf 'FAIL tracked key material filename: %s\n' "$path" >&2
            failures=$((failures + 1))
            ;;
    esac
done < <(git -C "$root" ls-files -z)

if [[ $failures -eq 0 ]]; then
    printf 'ok no obvious tracked secret or key material\n'
    exit 0
fi

printf 'FAIL secret scan: %d finding(s)\n' "$failures" >&2
exit 1
