#!/usr/bin/env bash

#################################################################
# WoltLab-Referenzen automatisch synchronisieren (nicht-interaktiv)
#
# Synchronisiert:
#   woltlab-docs, woltlab-github, woltlab-d-ts,
#   woltlab-exporter, woltlab-conversation, woltlab-legal-notice
# mit origin/<VERSION> (Standard: 6.2). Optional Core-ZIP via update-Skript.
#
# Manuell:
#   ./tools/sync-woltlab-references.sh
#   ./tools/sync-woltlab-references.sh 6.2
#   ./tools/update-woltlab-version.sh 6.2.6   # inkl. Core-Download
#
# Cron (wöchentlich, Sonntag 04:00):
#   0 4 * * 0 /pfad/zum/plugin-manager/tools/sync-woltlab-references.sh >> ~/.cache/woltlab-refs-sync.log 2>&1
#################################################################

set -e

TOOLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly TOOLS_DIR
MAIN_DIR="$(dirname "$TOOLS_DIR")"
export MAIN_DIR
# shellcheck source=woltlab-refs-lib.sh
source "$TOOLS_DIR/woltlab-refs-lib.sh"
VERSION="$(woltlab_preferred_line)"
if [[ "${1:-}" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then VERSION="$1"; shift; fi
exec "$TOOLS_DIR/update-woltlab-version.sh" --refs-only "$@" "$VERSION"
