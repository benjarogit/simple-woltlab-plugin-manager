#!/usr/bin/env python3
"""Tests for check-acp-template-assets.py."""
from __future__ import annotations

import subprocess
import os
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
SCRIPT = TOOLS / "check-acp-template-assets.py"


class AcpTemplateAssetsTests(unittest.TestCase):
    def test_missing_css_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "acptemplates").mkdir()
            (root / "acptemplates" / "demo.tpl").write_text(
                '<link rel="stylesheet" href="{unsafe:$__wcf->getPath()}acp/style/missing.css" />\n',
                encoding="utf-8",
            )
            self.assertEqual(subprocess.call([sys.executable, str(SCRIPT), str(root)]), 1)

    def test_present_css_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "acptemplates").mkdir()
            (root / "acptemplates" / "demo.tpl").write_text(
                '<link rel="stylesheet" href="{unsafe:$__wcf->getPath()}acp/style/ok.css?v=1" />\n',
                encoding="utf-8",
            )
            (root / "files" / "acp" / "style").mkdir(parents=True)
            (root / "files" / "acp" / "style" / "ok.css").write_text("a{}", encoding="utf-8")
            self.assertEqual(subprocess.call([sys.executable, str(SCRIPT), str(root)]), 0)

    def test_suite_asset_is_resolved_against_explicit_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "acptemplates").mkdir()
            (root / "acptemplates/demo.tpl").write_text('<script src="{@$__wcf->getPath()}js/3rdParty/chart.js"></script>')
            core = root / "suite"
            asset = core / "js/3rdParty/chart.js"
            asset.parent.mkdir(parents=True)
            env = {**os.environ, "WOLTLAB_CORE_REFERENCE": str(core)}
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(root)], env=env, capture_output=True).returncode, 1)
            asset.write_text("/* supplied by WCF */")
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(root)], env=env, capture_output=True).returncode, 0)

    def test_family_asset_requires_an_actual_dependency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            family = Path(tmp)
            addon, base = family / "addon", family / "base"
            (addon / "acptemplates").mkdir(parents=True)
            (base / "js/Shared").mkdir(parents=True)
            (base / "js/Shared/Copy.js").write_text("define([],()=>{});")
            (base / "package.xml").write_text('<package xmlns="http://www.woltlab.com" name="com.example.base"/>')
            (addon / "acptemplates/demo.tpl").write_text('<script>require(["Shared/Copy"]);</script>')
            manifest = family / "family.json"
            manifest.write_text('{"paths":["addon","base"]}')
            env = {**os.environ, "SWPM_FAMILY_MANIFEST": str(manifest)}
            package = addon / "package.xml"
            package.write_text('<package xmlns="http://www.woltlab.com" name="com.example.addon"><requiredpackages><requiredpackage>com.example.base</requiredpackage></requiredpackages></package>')
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(addon)], env=env, capture_output=True).returncode, 0)
            package.write_text('<package xmlns="http://www.woltlab.com" name="com.example.addon"/>')
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), str(addon)], env=env, capture_output=True).returncode, 1)


if __name__ == "__main__":
    unittest.main()
