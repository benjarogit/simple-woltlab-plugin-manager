#!/usr/bin/env python3
"""Tests for check-page-option-gates.py."""
from __future__ import annotations

import subprocess
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS / "check-page-option-gates.py"


class PageOptionGatesTests(unittest.TestCase):
    def test_detects_missing_page_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "option.xml").write_text(
                """<?xml version="1.0"?>
<data><import><options>
<option name="demo_active"><defaultvalue>0</defaultvalue></option>
<option name="demo_effect_banner"><defaultvalue>0</defaultvalue></option>
</options></import></data>
""",
                encoding="utf-8",
            )
            (root / "page.xml").write_text(
                """<?xml version="1.0"?>
<data xmlns="http://www.woltlab.com">
<import>
<page identifier="demo.Banner">
<controller>wcf\\page\\DemoBannerPage</controller>
<options>demo_active</options>
</page>
</import>
</data>
""",
                encoding="utf-8",
            )
            page_php = root / "files" / "lib" / "page" / "DemoBannerPage.class.php"
            page_php.parent.mkdir(parents=True)
            page_php.write_text(
                """<?php
namespace wcf\\page;
final class DemoBannerPage extends AbstractPage {
    public function checkModules() {
        parent::checkModules();
        if (!defined('DEMO_ACTIVE') || !DEMO_ACTIVE) {
            throw new \\wcf\\system\\exception\\IllegalLinkException();
        }
        if (!defined('DEMO_EFFECT_BANNER') || !DEMO_EFFECT_BANNER) {
            throw new \\wcf\\system\\exception\\IllegalLinkException();
        }
    }
    public function show() {}
}
""",
                encoding="utf-8",
            )
            self.assertEqual(subprocess.call([sys.executable, str(SCRIPT), str(root)]), 1)

    def test_aligned_gates_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "option.xml").write_text(
                """<?xml version="1.0"?>
<data><import><options>
<option name="demo_active"><defaultvalue>0</defaultvalue></option>
<option name="demo_effect_banner"><defaultvalue>0</defaultvalue></option>
</options></import></data>
""",
                encoding="utf-8",
            )
            (root / "page.xml").write_text(
                """<?xml version="1.0"?>
<data xmlns="http://www.woltlab.com">
<import>
<page identifier="demo.Banner">
<controller>wcf\\page\\DemoBannerPage</controller>
<options>demo_active,demo_effect_banner</options>
</page>
</import>
</data>
""",
                encoding="utf-8",
            )
            page_php = root / "files" / "lib" / "page" / "DemoBannerPage.class.php"
            page_php.parent.mkdir(parents=True)
            page_php.write_text(
                """<?php
namespace wcf\\page;
final class DemoBannerPage extends AbstractPage {
    public function checkModules() {
        if (!defined('DEMO_ACTIVE') || !DEMO_ACTIVE) { throw new \\Exception(); }
        if (!defined('DEMO_EFFECT_BANNER') || !DEMO_EFFECT_BANNER) { throw new \\Exception(); }
    }
    public function show() {}
}
""",
                encoding="utf-8",
            )
            self.assertEqual(subprocess.call([sys.executable, str(SCRIPT), str(root)]), 0)

    def test_rendering_constants_are_not_access_gates(self) -> None:
        spec = importlib.util.spec_from_file_location("gates", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            php = Path(tmp) / "Page.php"
            php.write_text("<?php class Page { public function readData(): void { $delay = DEMO_DELAY; } }")
            self.assertEqual(module.php_gate_options(php, {"demo_delay"}), set())

    def test_typed_nested_gate_does_not_scan_next_method(self) -> None:
        spec = importlib.util.spec_from_file_location("gates", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        text = "<?php class Page { public function checkModules(): void { if (DEMO_ACTIVE) { /* } */ $x = '}'; } if (!DEMO_FEATURE) { throw new Exception(); } } public function readData() { $x = DEMO_DELAY; } }"
        with tempfile.TemporaryDirectory() as tmp:
            php = Path(tmp) / "Page.php"
            php.write_text(text)
            self.assertEqual(module.php_gate_options(php, {"demo_active", "demo_feature", "demo_delay"}), {"demo_active", "demo_feature"})


if __name__ == "__main__":
    unittest.main()
