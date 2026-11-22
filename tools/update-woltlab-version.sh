#!/usr/bin/env bash
# Explicit package/line selection; side-by-side references and stable ZIPs.
set -euo pipefail
TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_DIR="$(dirname "$TOOLS_DIR")"
source "$TOOLS_DIR/woltlab-refs-lib.sh"
CHECK_ONLY=0 SKIP_CORE=0 VERSION="" PACKAGE="" MANIFEST="" LEGACY=0
usage() {
    cat <<'EOF'
Usage: update-woltlab-version.sh [--check] [--refs-only] [VERSION | --package PATH] [--manifest FILE]
  --check       Read-only status: exit0 current,2 update/missing,1 error.
  --refs-only   Explicit Git branch only; no stable ZIP implied by a dev line.
  VERSION       Explicit X.Y or stable X.Y.Z; latest patch only within this line.
  --package     Derive target line from this package's WCF compatibility metadata.
  --manifest    Explicit family for required-package compatibility resolution.
  --legacy-root --check only: inspect old manager-root references, never migrate them.
Default root: .references/X.Y. WOLTLAB_REFERENCES_ROOT selects an exact line-root.
WOLTLAB_REFERENCE_SOURCES optionally supplies an explicit source map for Git.
No version/package/WOLTLAB_REF_LINE means error; no implicit latest/default branch.
EOF
}
while (($#)); do
    case "$1" in
        --check) CHECK_ONLY=1 ;;
        --refs-only|--no-core) SKIP_CORE=1 ;;
        --legacy-root) LEGACY=1 ;;
        --yes|-y|--fresh) : ;; # Kept CLI compatibility; never infer a target.
        --package|--manifest)
            (($# >= 2)) || { usage >&2; exit 1; }
            if [[ "$1" == --package ]]; then PACKAGE="$2"; else MANIFEST="$2"; fi
            shift ;;
        --help|-h) usage; exit 0 ;;
        -*) usage >&2; exit 1 ;;
        *) [[ -z "$VERSION" ]] || { usage >&2; exit 1; }; VERSION="$1" ;;
    esac
    shift
done
if [[ -n "$VERSION" && ! "$VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo 'Invalid explicit version' >&2; exit 1
fi
if [[ -n "$PACKAGE" ]]; then
    args=(--target-line --package "$PACKAGE")
    [[ -z "$MANIFEST" ]] || args+=(--manifest "$MANIFEST")
    LINE="$(python3 "$TOOLS_DIR/woltlab-reference-selection.py" "${args[@]}")"
    if [[ -n "$VERSION" && "$(woltlab_line_from_version "$VERSION")" != "$LINE" ]]; then
        echo 'Explicit version conflicts with package target line' >&2; exit 1
    fi
else
    VERSION="${VERSION:-$(woltlab_preferred_line || true)}"
    [[ -n "$VERSION" ]] || { echo 'Explicit VERSION or --package required' >&2; exit 1; }
    [[ "$VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo 'Invalid explicit version' >&2; exit 1; }
    LINE="$(woltlab_line_from_version "$VERSION")"
fi
if (( LEGACY )); then
    (( CHECK_ONLY )) || { echo '--legacy-root is read-only' >&2; exit 1; }
    REF_ROOT="$MAIN_DIR"
else
    REF_ROOT="$(woltlab_reference_root "$LINE")"
fi
export WOLTLAB_REFERENCES_ROOT="$REF_ROOT"
REF_ARGS=(--root "$REF_ROOT" --line "$LINE")
[[ -z "${WOLTLAB_REFERENCE_SOURCES:-}" ]] || REF_ARGS+=(--sources "$WOLTLAB_REFERENCE_SOURCES")
# Preflight all references before a Core download or any reference mutation.
rc=0
python3 "$TOOLS_DIR/sync-woltlab-git.py" "${REF_ARGS[@]}" --check || rc=$?
(( rc != 1 )) || exit 1
if (( CHECK_ONLY )); then
    (( ! SKIP_CORE )) || exit "$rc"
    wanted="$VERSION"
    if [[ -z "$wanted" || "$wanted" == "$LINE" ]]; then
        online="$(woltlab_pick_latest_release "$LINE")" || { echo "No stable Core ZIP for $LINE; use --refs-only" >&2; exit 1; }
        wanted="${online%%$'\t'*}"
    fi
    if [[ ! -e "$REF_ROOT/woltlab-core" ]]; then exit 2; fi
    python3 "$TOOLS_DIR/woltlab-reference-selection.py" --check-core --root "$REF_ROOT" --version "$wanted" >/dev/null || exit 1
    exit "$rc"
fi
if (( ! SKIP_CORE )); then
    "$TOOLS_DIR/download-woltlab-core.sh" "${VERSION:-$LINE}"
fi
python3 "$TOOLS_DIR/sync-woltlab-git.py" "${REF_ARGS[@]}"
