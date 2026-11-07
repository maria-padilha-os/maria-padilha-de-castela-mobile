#!/usr/bin/env bash
# Check required host tools for a profile without installing anything.

set -euo pipefail

# shellcheck source=lib.sh
. "$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

profile="ci"
list_only=0
json=0
quiet=0

usage() {
    cat <<'EOF'
Usage: scripts/check-tools.sh [--profile ci|build|sign] [--list] [--json] [--quiet]

Checks command availability only. It does not install packages, run sudo, or
change the host. Profiles are declared in config/tools.tsv.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            [[ $# -ge 2 ]] || die "--profile requires a value"
            profile="$2"
            shift 2
            ;;
        --list)
            list_only=1
            shift
            ;;
        --json)
            json=1
            shift
            ;;
        --quiet)
            quiet=1
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

[[ "$profile" =~ ^[a-z]+$ ]] || die "invalid profile: $profile"
[[ -r "$CONFIG_DIR/tools.tsv" ]] || die "missing config/tools.tsv"

tools=()
selected_reasons=()
while IFS=$'\t' read -r tool profiles reason; do
    [[ -z "${tool:-}" ]] && continue
    [[ "$tool" == \#* ]] && continue
    case " $profiles " in
        *" $profile "*) ;;
        *) continue ;;
    esac
    tools+=("$tool")
    selected_reasons+=("${reason:-required}")
done <"$CONFIG_DIR/tools.tsv"

[[ ${#tools[@]} -gt 0 ]] || die "no tools declared for profile: $profile"

if [[ $list_only -eq 1 ]]; then
    printf '%s\n' "${tools[@]}"
    exit 0
fi

missing=()
missing_reasons=()
for index in "${!tools[@]}"; do
    tool="${tools[$index]}"
    if ! command -v "$tool" >/dev/null 2>&1; then
        missing+=("$tool")
        missing_reasons+=("${selected_reasons[$index]}")
    fi
done

if [[ $json -eq 1 ]]; then
    printf '{"profile":"%s","ok":%s,"checked":%d,"missing":[' \
        "$profile" "$([[ ${#missing[@]} -eq 0 ]] && echo true || echo false)" "${#tools[@]}"
    for index in "${!missing[@]}"; do
        [[ $index -gt 0 ]] && printf ','
        printf '"%s"' "${missing[$index]}"
    done
    printf ']}\n'
else
    if [[ $quiet -eq 0 ]]; then
        printf 'profile %s: %d tool(s) checked\n' "$profile" "${#tools[@]}"
    fi
    for index in "${!tools[@]}"; do
        tool="${tools[$index]}"
        if command -v "$tool" >/dev/null 2>&1; then
            [[ $quiet -eq 1 ]] || printf 'ok tool %s\n' "$tool"
        else
            printf 'missing tool %s (%s)\n' "$tool" "${selected_reasons[$index]}" >&2
        fi
    done
    if [[ ${#missing[@]} -eq 0 ]]; then
        [[ $quiet -eq 1 ]] || printf 'ok profile %s\n' "$profile"
    else
        printf 'FAIL profile %s: %d missing tool(s)\n' "$profile" "${#missing[@]}" >&2
    fi
fi

[[ ${#missing[@]} -eq 0 ]]
