#!/usr/bin/env bash
# Provision exact stable setup archives in an explicitly selected reference line.
set -euo pipefail
TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN_DIR="$(dirname "$TOOLS_DIR")"
source "$TOOLS_DIR/woltlab-refs-lib.sh"
VERSION="${1:-$(woltlab_preferred_line || true)}"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]] || { echo 'Explicit X.Y or X.Y.Z required' >&2; exit 1; }
LINE="$(woltlab_line_from_version "$VERSION")"
if [[ "$VERSION" == "$LINE" ]]; then
    online="$(woltlab_pick_latest_release "$LINE")" || { echo "No stable Core ZIP for $LINE; no fallback" >&2; exit 1; }
    VERSION="${online%%$'\t'*}"
fi
REF_ROOT="$(woltlab_reference_root "$LINE")"
URL="$(woltlab_asset_url_for_version "$VERSION")"
TEMP_ARCHIVE="$(mktemp)"
trap 'rm -f -- "$TEMP_ARCHIVE"' EXIT
curl --fail --silent --show-error --location --output "$TEMP_ARCHIVE" "$URL"
python3 "$TOOLS_DIR/woltlab-reference-selection.py" --install-core "$VERSION" --root "$REF_ROOT" --archive "$TEMP_ARCHIVE" --url "$URL"
