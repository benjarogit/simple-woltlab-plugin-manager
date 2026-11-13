"""A family build must compile its requested package, never another auto-discovered slot."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1]


class TypeScriptSelectionTests(unittest.TestCase):
    def test_explicit_package_wins_over_first_discovered_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / 'tools'
            tools.mkdir()
            shutil.copy2(TOOLS / 'typescript.sh', tools / 'typescript.sh')
            selected = root / 'zzz/temp_edit'
            wrong = root / 'aaa/temp_edit'
            for package in [selected, wrong]:
                (package / 'node_modules').mkdir(parents=True)
                (package / 'ts/Feature').mkdir(parents=True)
                (package / 'package.json').write_text('{}')
                (package / 'tsconfig.json').write_text('{}')
                (package / 'ts/Feature/Main.ts').write_text('export const x = 1;')
            binary = root / 'bin'
            binary.mkdir()
            npx = binary / 'npx'
            npx.write_text('#!/bin/sh\nmkdir -p js/Feature\nprintf "compiled" > js/Feature/Main.js\n')
            npx.chmod(0o755)
            result = subprocess.run(['bash', str(tools / 'typescript.sh'), '--plugin', str(selected)],
                                    env={**os.environ, 'PATH': str(binary) + ':' + os.environ['PATH']},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((selected / 'js/Feature/Main.js').is_file())
            self.assertFalse((wrong / 'js').exists())


if __name__ == '__main__':
    unittest.main()
