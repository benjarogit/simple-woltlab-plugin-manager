#!/usr/bin/env python3
"""Fail when ACP templates reference stylesheets/scripts that are missing from the package.

Learned from ACP previews: `<link href="{…}acp/style/foo.css">` compiles,
but if the file is absent from files/ the ACP looks broken after install/update.
"""
from __future__ import annotations

import re
import os
import json
import xml.etree.ElementTree as ET
from functools import lru_cache
import sys
from pathlib import Path

# Full relative path after getPath() / static path in quotes
LINK_ASSET = re.compile(
    r"""(?:href|src)\s*=\s*["'][^"']*?\b((?:acp/)?(?:style|js)/[a-zA-Z0-9_./-]+\.(?:css|js))""",
    re.I,
)
REQUIRE_MOD = re.compile(r"""require\(\s*\[\s*["']([A-Za-z][A-Za-z0-9_/]+)["']\s*\]""")


def template_dirs(root: Path) -> list[Path]:
    dirs = [
        root / "acptemplates",
        root / "acpTemplates",
        root / "files" / "acp" / "templates",
    ]
    return [d for d in dirs if d.is_dir()]


@lru_cache(maxsize=None)
def required_sources(root: Path) -> tuple[Path, ...]:
    manifest = os.environ.get("SWPM_FAMILY_MANIFEST", os.environ.get("WOLTLAB_FAMILY_MANIFEST", ""))
    if not manifest:
        return ()
    source = Path(manifest).resolve()
    data = json.loads(source.read_text())
    ns = {"w": "http://www.woltlab.com"}
    package = ET.parse(root / "package.xml").getroot()
    required = {(node.text or "").strip() for node in package.findall("w:requiredpackages/w:requiredpackage", ns)}
    result = []
    for rel in data.get("paths", []):
        candidate = (source.parent / rel).resolve()
        if candidate == root.resolve():
            continue
        metadata = ET.parse(candidate / "package.xml").getroot()
        if metadata.get("name") in required:
            result.append(candidate)
    return tuple(result)


def asset_exists(root: Path, rel: str) -> bool:
    candidates = [
        root / "files" / rel,
        root / "files_wcf" / rel,
        root / rel,
    ]
    for dependency in required_sources(root):
        candidates.extend([dependency / rel, dependency / "files" / rel, dependency / "files_wcf" / rel])
    return any(p.is_file() for p in candidates)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    dirs = template_dirs(root)
    if not dirs:
        return 0

    issues: list[str] = []
    for base in dirs:
        for path in sorted(base.rglob("*.tpl")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                issues.append(f"{path.relative_to(root)}: read-error: {exc}")
                continue
            rel_tpl = path.relative_to(root)

            for match in LINK_ASSET.finditer(text):
                rel = match.group(1)
                if asset_exists(root, rel):
                    continue
                if "__wcf->getPath()" in match.group(0):
                    core = Path(os.environ.get("WOLTLAB_CORE_REFERENCE", os.environ.get("WOLTLAB_ROOT", str(Path(__file__).resolve().parents[1] / "woltlab-github/wcfsetup/install/files"))))
                    if not (core / rel).is_file():
                        issues.append(f"{rel_tpl}: missing WCF reference asset {rel}")
                elif not asset_exists(root, rel):
                    issues.append(f"{rel_tpl}: missing asset files/{rel}")

            for mod in REQUIRE_MOD.findall(text):
                # Suite core modules ship with WCF, not the plugin package.
                if mod.startswith("WoltLabSuite/") or mod.startswith("WCF."):
                    continue
                js = f"js/{mod}.js"
                acp_js = f"acp/js/{mod}.js"
                if not (asset_exists(root, js) or asset_exists(root, acp_js)):
                    issues.append(f"{rel_tpl}: missing AMD module files/{js}")

    seen: set[str] = set()
    for line in issues:
        if line in seen:
            continue
        seen.add(line)
        print(line)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
