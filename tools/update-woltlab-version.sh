#!/usr/bin/env bash
# Explicit branch references and stable Core downloads are separate operations.
set -euo pipefail
TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_DIR="$(dirname "$TOOLS_DIR")"
# shellcheck source=woltlab-refs-lib.sh
source "$TOOLS_DIR/woltlab-refs-lib.sh"
CHECK_ONLY=0
SKIP_CORE=0
ASSUME_YES=0
VERSION=""
usage() {
    cat <<'EOF'
Usage: update-woltlab-version.sh [--check] [--refs-only] [--yes] [--fresh] [VERSION]
  --check      Read-only status: exit 0 current, 2 update/missing, 1 error.
  --refs-only  Git references only; supports development branches such as 6.3.
  VERSION      major.minor or a numeric stable patch version.
  --yes        Accept interactive update prompt when VERSION is omitted.
  --fresh      Ignore release cache (check mode never writes it).
WOLTLAB_REFERENCES_ROOT selects the reference directory (default: manager root).
WOLTLAB_REFERENCE_SOURCES optionally selects a JSON source map.
A Git development branch does not imply an available stable Core ZIP.
EOF
}
while (($#)); do
    case "$1" in
        --check) CHECK_ONLY=1 ;;
        --refs-only|--no-core) SKIP_CORE=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --fresh) : ;; # Release status is always read directly without a cache.
        --help|-h) usage; exit 0 ;;
        -*) usage >&2; exit 1 ;;
        *) if [[ -n "$VERSION" ]]; then usage >&2; exit 1; fi; VERSION="$1" ;;
    esac
    shift
done
if [[ -n "$VERSION" && ! "$VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Invalid version: $VERSION" >&2
    exit 1
fi
REF_ROOT="${WOLTLAB_REFERENCES_ROOT:-$MAIN_DIR}"
LINE="${VERSION:-$(woltlab_preferred_line)}"
LINE="$(woltlab_line_from_version "$LINE")"
REF_ARGS=(--root "$REF_ROOT" --line "$LINE")
if [[ -n "${WOLTLAB_REFERENCE_SOURCES:-}" ]]; then
    REF_ARGS+=(--sources "$WOLTLAB_REFERENCE_SOURCES")
fi
if (( CHECK_ONLY )); then
    rc=0
    python3 "$TOOLS_DIR/sync-woltlab-git.py" "${REF_ARGS[@]}" --check || rc=$?
    if (( SKIP_CORE )); then exit "$rc"; fi
    # Do not source common.sh/create logs, fetch Git refs, or write a release cache.
    if ! online="$(woltlab_pick_latest_release "$LINE")"; then
        echo "No stable Core ZIP found for $LINE; use --refs-only for development references." >&2
        exit 1
    fi
    wanted="${VERSION:-${online%%$'\t'*}}"
    local_version="$(woltlab_local_core_version || true)"
    echo "Stable Core: local=${local_version:-missing}, requested=$wanted"
    if (( rc == 1 )); then exit 1; fi
    if [[ "$VERSION" == "$LINE" || -z "$VERSION" ]]; then wanted="${online%%$'\t'*}"; fi
    if [[ "$local_version" != "$wanted" ]]; then rc=2; fi
    exit "$rc"
fi
if [[ -z "$VERSION" && "$ASSUME_YES" -ne 1 ]]; then
    if [[ ! -t 0 ]]; then
        echo "Use --check for status, or pass VERSION/--yes to synchronize." >&2
        exit 1
    fi
    read -r -p "Synchronize references for $LINE? [y/N] " answer
    [[ "$answer" =~ ^[jJyY]$ ]] || exit 0
fi
# Release download failure must not be reported as successful synchronization.
if (( ! SKIP_CORE )); then
    if ! online="$(woltlab_pick_latest_release "$LINE")"; then
        echo "No stable Core ZIP found for $LINE; use --refs-only for development references." >&2
        exit 1
    fi
    core="${VERSION:-${online%%$'\t'*}}"
    [[ "$core" == "$LINE" ]] && core="${online%%$'\t'*}"
    # Existing downloader owns its logs and release cache; only called for mutation.
    "$TOOLS_DIR/download-woltlab-core.sh" "$core"
fi
# Sync has no hard reset, replacement of user directories, or default-branch fallback.
python3 "$TOOLS_DIR/sync-woltlab-git.py" "${REF_ARGS[@]}"
