#!/usr/bin/env python3
"""Warn/fail when page.xml option gates disagree with Page::checkModules() / option.xml.

Learned from feature-gated pages: page listed only `cherrymagic_active` while
PHP also required `cherrymagic_effect_status_signature`. Prefer aligning page `<options>`
with the PHP gate (AND of all feature toggles).
"""
from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

OPTION_DEFAULT = re.compile(
    r"<option\s+name=\"([^\"]+)\">",
)
CHECK_MODULES = re.compile(
    r"function\s+checkModules\s*\([^)]*\)\s*(?::\s*[?\w\\|]+\s*)?\{",
    re.M,
)


def module_body(text: str) -> str:
    match = CHECK_MODULES.search(text)
    if not match:
        return ""
    # Match braces while ignoring PHP strings and comments; retain offsets into original.
    tokens = re.compile(r"'(?:(?:\\.)|[^'\\])*'|\"(?:(?:\\.)|[^\"\\])*\"|/\*.*?\*/|//[^\n]*|[{}]", re.S)
    depth = 1
    for token in tokens.finditer(text, match.end()):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return text[match.end():token.start()]
    return ""


CONST_REF = re.compile(
    r"(?:'([A-Z][A-Z0-9_]*)'\|defined)|"
    r"\bdefined\(\s*'([A-Z][A-Z0-9_]*)'\s*\)|"
    r"\b([A-Z][A-Z0-9_]{4,})\b"
)


def local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def option_names(root: Path) -> set[str]:
    path = root / "option.xml"
    if not path.is_file():
        return set()
    return set(OPTION_DEFAULT.findall(path.read_text(encoding="utf-8", errors="replace")))


def const_to_option(const: str) -> str:
    return const.lower()


def page_entries(root: Path) -> list[tuple[str, str, list[str]]]:
    path = root / "page.xml"
    if not path.is_file():
        return []
    tree = ET.parse(path)
    rows: list[tuple[str, str, list[str]]] = []
    for page in tree.iter():
        if local(page.tag) != "page":
            continue
        ident = page.get("identifier") or "unknown"
        controller = ""
        options: list[str] = []
        for child in page:
            t = local(child.tag)
            if t == "controller" and child.text:
                controller = child.text.strip()
            elif t == "options" and child.text:
                options = [o.strip() for o in child.text.split(",") if o.strip()]
        if controller:
            rows.append((ident, controller, options))
    return rows


def controller_path(root: Path, fqn: str) -> Path | None:
    # wcf\page\Foo → files/lib/page/Foo.class.php
    parts = fqn.replace("\\", "/").split("/")
    if len(parts) < 2:
        return None
    # drop vendor app prefix (wcf)
    rel = "/".join(parts[1:]) + ".class.php"
    for base in (root / "files" / "lib", root / "files_wcf" / "lib", root / "lib"):
        cand = base / rel
        if cand.is_file():
            return cand
    return None


def php_gate_options(path: Path, known: set[str]) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # A constant used for rendering/redirect timing is not a module access gate.
    body = module_body(text)
    if not body:
        return set()
    found: set[str] = set()
    for cm in CONST_REF.finditer(body):
        c = cm.group(1) or cm.group(2) or cm.group(3)
        if not c:
            continue
        if c in {"AVAILABLE_DURING_OFFLINE_MODE", "HTTP_IF_NONE_MATCH"}:
            continue
        opt = const_to_option(c)
        if opt in known:
            found.add(opt)
    return found


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    pages = page_entries(root)
    if not pages:
        return 0

    known = option_names(root)
    issues: list[str] = []

    for ident, controller, page_opts in pages:
        php_path = controller_path(root, controller)
        if php_path is None:
            continue
        php_opts = php_gate_options(php_path, known)
        if not php_opts:
            continue
        page_set = set(page_opts)
        missing_on_page = sorted(php_opts - page_set)
        unknown_on_page = sorted(o for o in page_opts if o not in known)
        if missing_on_page:
            issues.append(
                f"page '{ident}': <options> missing PHP checkModules gate(s): "
                + ", ".join(missing_on_page)
            )
        if unknown_on_page:
            issues.append(
                f"page '{ident}': <options> unknown option name(s): "
                + ", ".join(unknown_on_page)
            )

    for line in issues:
        print(line)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
