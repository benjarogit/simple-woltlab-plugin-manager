#!/usr/bin/env bash
# Run SWPM toolkit unit/smoke tests (no external test frameworks required).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fail=0

echo "== bash: common helpers =="
if ! bash "$SCRIPT_DIR/test_common_helpers.sh"; then
    fail=1
fi

echo "== python: package PIP archives =="
if ! python3 "$SCRIPT_DIR/test_check_package_pip_archives.py"; then
    fail=1
fi

echo "== python: empty pack dirs =="
if ! python3 "$SCRIPT_DIR/test_check_empty_pack_dirs.py"; then
    fail=1
fi

echo "== python: language PIP keys =="
if ! python3 "$SCRIPT_DIR/test_check_language_pip_keys.py"; then
    fail=1
fi

echo "== python: reference synchronization =="
if ! python3 "$SCRIPT_DIR/test_reference_sync.py"; then
    fail=1
fi

echo "== python: WCF package requirement =="
if ! python3 "$SCRIPT_DIR/test_core_requirement.py"; then
    fail=1
fi

echo "== python: isolated target reference selection =="
if ! python3 "$SCRIPT_DIR/test_reference_selection.py"; then
    fail=1
fi

echo "== python: explicit TypeScript package selection =="
if ! python3 "$SCRIPT_DIR/test_typescript_selection.py"; then
    fail=1
fi

echo "== python: ACP template assets =="
if ! python3 "$SCRIPT_DIR/test_check_acp_template_assets.py"; then
    fail=1
fi

echo "== python: page option gates =="
if ! python3 "$SCRIPT_DIR/test_check_page_option_gates.py"; then
    fail=1
fi

if (( fail )); then
    echo "tools/tests: FAILED"
    exit 1
fi
echo "tools/tests: OK"
exit 0
