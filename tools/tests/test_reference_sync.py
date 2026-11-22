"""Regression tests use local Git repositories; no network or live suite."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import os
import importlib.util
import shutil

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
        self.assertEqual(self.run_sync('--check').returncode,0)

    def test_lock_line_conflict_and_symlink_are_protected_without_writes(self):
        self.root.mkdir()
        lock=self.root/'reference-lock.json'
        lock.write_text(json.dumps({'schema':1,'line':'6.2','references':[]}))
        before=self.fingerprint()
        self.assertEqual(self.run_sync('--check').returncode,1)
        self.assertEqual(self.run_sync().returncode,1)
        self.assertEqual(before,self.fingerprint())
        lock.unlink()
        external=self.base/'external';external.mkdir()
        (self.root/'sample').symlink_to(external,target_is_directory=True)
        self.assertEqual(self.run_sync().returncode,1)
        self.assertFalse(list(external.iterdir()))

    def test_local_commit_in_check_mode_writes_nothing(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample'
        self.git(checkout,'config','user.email','tests@example.invalid');self.git(checkout,'config','user.name','Test')
        (checkout/'source.txt').write_text('local only')
        self.git(checkout,'commit','-am','local')
        before=self.fingerprint()
        self.assertEqual(self.run_sync('--check').returncode,1)
        self.assertEqual(before,self.fingerprint())

    def test_previous_lock_is_archived_exactly_on_update(self):
        self.assertEqual(self.run_sync().returncode,0)
        old=(self.root/'reference-lock.json').read_bytes()
        (self.origin/'source.txt').write_text('next')
        self.git(self.origin,'commit','-am','next')
        self.assertEqual(self.run_sync().returncode,0)
        self.assertIn(old,[p.read_bytes() for p in (self.root/'history').glob('reference-lock-*.json')])

    def test_direct_sync_rejects_ancestor_symlink_before_network_or_writes(self):
        outside=self.base/'outside';outside.mkdir()
        link=self.base/'alias';link.symlink_to(outside,target_is_directory=True)
        self.root=link/'deep/references'
        self.sources.write_text(json.dumps({'sample':str(self.base/'no-network-source')}))
        for args in [(),('--check',)]:
            result=self.run_sync(*args)
            self.assertEqual(result.returncode,1)
            self.assertIn('ancestor symlink',result.stderr)
            self.assertFalse(list(outside.iterdir()))

    def test_redirected_core_worktree_is_rejected_without_outside_or_lock_writes(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample';outside=self.base/'outside';outside.mkdir()
        (outside/'source.txt').write_text('initial\n')
        self.git(checkout,'config','core.worktree',str(outside))
        (self.origin/'source.txt').write_text('upstream second\n');self.git(self.origin,'commit','-am','second')
        before=self.fingerprint();outside_before=(outside/'source.txt').read_bytes()
        for args in [('--check',),()]:
            result=self.run_sync(*args)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('worktree boundary',result.stdout)
            self.assertEqual(self.fingerprint(),before)
            self.assertEqual((outside/'source.txt').read_bytes(),outside_before)
            self.assertEqual((checkout/'source.txt').read_text(),'initial\n')

    def test_worktree_redirect_after_inspect_is_rechecked_before_first_fetch(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample'
        (self.origin/'source.txt').write_text('upstream second\n');self.git(self.origin,'commit','-am','second')
        spec=importlib.util.spec_from_file_location('sync_boundary_test',TOOLS/'sync-woltlab-git.py')
        sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)
        rows=sync.inspect(self.root,'6.3',{'sample':str(self.origin)})
        self.assertEqual(rows[0]['status'],'update')
        outside=self.base/'outside';outside.mkdir();(outside/'source.txt').write_text('initial\n')
        self.git(checkout,'config','core.worktree',str(outside))
        before=self.fingerprint()
        self.assertFalse(sync.synchronize(self.root,'6.3',rows))
        self.assertEqual(self.fingerprint(),before)
        self.assertEqual((outside/'source.txt').read_text(),'initial\n')
        self.assertEqual(rows[0]['status'],'error')

    def test_own_core_worktree_setting_and_clean_clone_can_fast_forward(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample';self.git(checkout,'config','core.worktree',str(checkout))
        (self.origin/'source.txt').write_text('allowed second\n');self.git(self.origin,'commit','-am','second')
        result=self.run_sync()
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((checkout/'source.txt').read_text(),'allowed second\n')
        self.assertEqual(self.run_sync('--check').returncode,0)

    def test_redirected_refs_metadata_rejects_inspect_and_after_inspect_before_fetch(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample'
        (self.origin/'source.txt').write_text('upstream second\n');self.git(self.origin,'commit','-am','second')
        spec=importlib.util.spec_from_file_location('sync_refs_escape',TOOLS/'sync-woltlab-git.py')
        sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)
        rows=sync.inspect(self.root,'6.3',{'sample':str(self.origin)})
        self.assertEqual(rows[0]['status'],'update')
        outside=self.base/'outside-refs';shutil.move(str(checkout/'.git/refs'),outside)
        (checkout/'.git/refs').symlink_to(outside,target_is_directory=True)
        def outside_bytes():
            return {str(p.relative_to(outside)):p.read_bytes() for p in outside.rglob('*') if p.is_file()}
        before=outside_bytes();lock=(self.root/'reference-lock.json').read_bytes();head=self.git(checkout,'rev-parse','HEAD')
        self.assertFalse(sync.synchronize(self.root,'6.3',rows))
        self.assertEqual(outside_bytes(),before);self.assertEqual((self.root/'reference-lock.json').read_bytes(),lock)
        self.assertEqual(self.git(checkout,'rev-parse','HEAD'),head)
        self.assertEqual(sync.inspect(self.root,'6.3',{'sample':str(self.origin)})[0]['status'],'error')

    def test_logs_fetch_head_packed_refs_and_mutable_hardlinks_are_protected(self):
        self.assertEqual(self.run_sync().returncode,0)
        checkout=self.root/'sample'
        spec=importlib.util.spec_from_file_location('sync_metadata_escape',TOOLS/'sync-woltlab-git.py')
        sync=importlib.util.module_from_spec(spec);spec.loader.exec_module(sync)
        for name in ['logs','FETCH_HEAD','packed-refs']:
            source=checkout/'.git'/name
            if not source.exists(): source.write_bytes(b'fixture metadata')
            outside=self.base/('outside-'+name);shutil.move(str(source),outside)
            source.symlink_to(outside,target_is_directory=outside.is_dir())
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'metadata symlink'):sync.git_boundary(checkout)
            source.unlink();shutil.move(str(outside),source)
        source=checkout/'.git/FETCH_HEAD';outside=self.base/'linked-fetch-head';os.link(source,outside)
        before=outside.read_bytes()
        with self.assertRaisesRegex(ValueError,'metadata hardlink'):sync.git_boundary(checkout)
        self.assertEqual(outside.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
