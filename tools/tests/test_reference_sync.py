"""Regression tests use local Git repositories; no network or live suite."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import os

TOOLS = Path(__file__).resolve().parents[1]


class ReferenceSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.origin = self.base / 'origin'
        self.origin.mkdir()
        self.git(self.origin, 'init', '-b', '6.3')
        self.git(self.origin, 'config', 'user.email', 'tests@example.invalid')
        self.git(self.origin, 'config', 'user.name', 'Test')
        (self.origin / 'source.txt').write_text('initial\n')
        self.git(self.origin, 'add', '.')
        self.git(self.origin, 'commit', '-m', 'initial')
        self.root = self.base / 'references'
        self.sources = self.base / 'sources.json'
        self.sources.write_text(json.dumps({'sample': str(self.origin)}))

    def git(self, cwd, *args):
        return subprocess.check_output(['git', '-C', str(cwd), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def run_sync(self, *args, shell=False):
        env = {**os.environ, 'WOLTLAB_REFERENCES_ROOT': str(self.root),
               'WOLTLAB_REFERENCE_SOURCES': str(self.sources)}
        command = ['bash', str(TOOLS / 'update-woltlab-version.sh'), '--refs-only', *args, '6.3'] if shell else [
            'python3', str(TOOLS / 'sync-woltlab-git.py'), '--root', str(self.root),
            '--line', '6.3', '--sources', str(self.sources), *args]
        return subprocess.run(command, env=env, text=True, capture_output=True)

    def fingerprint(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_explicit_shell_check_does_not_create_missing_root(self):
        result = self.run_sync('--check', shell=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(self.root.exists())

    def test_sync_pins_commit_and_check_changes_no_files(self):
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        expected = self.git(self.origin, 'rev-parse', 'HEAD')
        self.assertEqual(self.git(self.root / 'sample', 'rev-parse', 'HEAD'), expected)
        lock = json.loads((self.root / 'reference-lock.json').read_text())
        self.assertEqual(lock['references'][0]['local_commit'], expected)
        before = self.fingerprint()
        self.assertEqual(self.run_sync('--check', shell=True).returncode, 0)
        self.assertEqual(before, self.fingerprint())

    def test_dirty_checkout_is_preserved(self):
        self.assertEqual(self.run_sync().returncode, 0)
        source = self.root / 'sample/source.txt'
        source.write_text('local work\n')
        before = self.fingerprint()
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertEqual(before, self.fingerprint())

    def test_local_commit_is_preserved(self):
        self.assertEqual(self.run_sync().returncode, 0)
        checkout = self.root / 'sample'
        self.git(checkout, 'config', 'user.email', 'tests@example.invalid')
        self.git(checkout, 'config', 'user.name', 'Test')
        (checkout / 'source.txt').write_text('local commit\n')
        self.git(checkout, 'commit', '-am', 'local only')
        head = self.git(checkout, 'rev-parse', 'HEAD')
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertEqual(head, self.git(checkout, 'rev-parse', 'HEAD'))

    def test_missing_branch_does_not_fallback_or_claim_success(self):
        self.git(self.origin, 'branch', '-m', '6.2')
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertFalse(self.root.exists())

    def test_user_directory_is_not_replaced(self):
        protected = self.root / 'sample'
        protected.mkdir(parents=True)
        (protected / 'important.txt').write_text('keep')
        before = self.fingerprint()
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertEqual(before, self.fingerprint())

    def test_preflight_failure_does_not_partially_clone(self):
        self.sources.write_text(json.dumps({'sample': str(self.origin), 'missing': str(self.base / 'absent')}))
        self.assertEqual(self.run_sync().returncode, 1)
        self.assertFalse(self.root.exists())

    def test_fast_forward_preserves_old_commit_and_pins_new(self):
        self.assertEqual(self.run_sync().returncode, 0)
        (self.origin / 'source.txt').write_text('upstream\n')
        self.git(self.origin, 'commit', '-am', 'next')
        result = self.run_sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.root / 'sample', 'rev-parse', 'HEAD'), self.git(self.origin, 'rev-parse', 'HEAD'))


if __name__ == '__main__':
    unittest.main()
