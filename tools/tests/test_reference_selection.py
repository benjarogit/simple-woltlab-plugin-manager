"""Version-isolated selection and exact Core archive fixtures, no network/live Suite."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
import zipfile

TOOLS=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('refs_selection',TOOLS/'woltlab-reference-selection.py')
refs=importlib.util.module_from_spec(spec);spec.loader.exec_module(refs)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.manager=self.root/'manager';self.manager.mkdir()

    def git(self,path,*args):
        return subprocess.check_output(['git','-C',str(path),*args],stderr=subprocess.DEVNULL,text=True).strip()

    def package(self,minimum='6.3.0 dev 1',excluded='7.0.0 Alpha 1',name='sample'):
        path=self.root/name;path.mkdir()
        (path/'package.xml').write_text(f'<package name="com.vendor.{name}"><packageinformation><version>1.0.0</version></packageinformation><requiredpackages><requiredpackage minversion="{minimum}">com.woltlab.wcf</requiredpackage></requiredpackages><excludedpackages><excludedpackage version="{excluded}">com.woltlab.wcf</excludedpackage></excludedpackages></package>')
        return path

    def provision(self,line,version=None):
        root=self.manager/'.references'/line;root.mkdir(parents=True)
        rows=[]
        for name in refs.REQUIRED:
            path=root/name;path.mkdir()
            self.git(path,'init','-b',line);self.git(path,'config','user.name','Test');self.git(path,'config','user.email','test@example.invalid')
            if name=='woltlab-github':
                file=path/'wcfsetup/install/files/lib/system/WCF.class.php';file.parent.mkdir(parents=True)
                file.write_text("<?php define('WCF_VERSION', '"+(version or line+'.0')+"');")
            else:(path/'source').write_text('reference')
            self.git(path,'add','.');self.git(path,'commit','-m','fixture')
            self.git(path,'remote','add','origin','https://example.invalid/'+name)
            rows.append(dict(name=name,path=str(path),branch=line,url='https://example.invalid/'+name,local_commit=self.git(path,'rev-parse','HEAD')))
        (root/'reference-lock.json').write_text(json.dumps(dict(schema=1,line=line,references=rows)))
        return root

    def fingerprint(self,root):
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}

    def test_three_target_lines_are_isolated_and_selection_is_read_only(self):
        for line in ['6.1','6.2','6.3']:
            package=self.package(line+'.0',name='p'+line.replace('.',''))
            selected=self.provision(line)
            before=self.fingerprint(self.manager)
            result=refs.select(package,manager=self.manager)
            self.assertEqual(result['line'],line);self.assertEqual(Path(result['root']),selected)
            self.assertEqual(before,self.fingerprint(self.manager))

    def test_no_latest_or_manager_root_fallback(self):
        package=self.package('6.2.0')
        self.provision('6.3')
        with self.assertRaises(OSError):refs.select(package,manager=self.manager)
        with self.assertRaises(ValueError):refs.line_of('latest')
        isolated_tools=self.manager/'tools';isolated_tools.mkdir()
        for name in ['update-woltlab-version.sh','woltlab-refs-lib.sh','woltlab-reference-selection.py']:
            shutil.copy2(TOOLS/name,isolated_tools/name)
        result=subprocess.run(['bash',str(isolated_tools/'update-woltlab-version.sh'),'--refs-only','--check'],capture_output=True,text=True,env={k:v for k,v in os.environ.items() if k!='WOLTLAB_REF_LINE'})
        self.assertEqual(result.returncode,1);self.assertIn('Explicit',result.stderr)

    def test_preferred_line_uses_only_explicit_configuration_not_old_download(self):
        tools=self.manager/'tools';tools.mkdir()
        core=self.manager/'woltlab-core';core.mkdir();(core/'.swpm-core-version').write_text('6.2.6')
        env={k:v for k,v in os.environ.items() if k!='WOLTLAB_REF_LINE'}
        script='TOOLS_DIR="$1"; MAIN_DIR="$2"; source "$3"; woltlab_preferred_line'
        command=['bash','-c',script,'fixture',str(tools),str(self.manager),str(TOOLS/'woltlab-refs-lib.sh')]
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,1);self.assertEqual(result.stdout,'')
        (tools/'.env').write_text('WOLTLAB_REF_LINE=6.1\n')
        result=subprocess.run(command,env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0);self.assertEqual(result.stdout,'6.1\n')

    def status(self,line,explicit=None,online=None):
        tools=self.manager/'tools';tools.mkdir(exist_ok=True)
        env={k:v for k,v in os.environ.items() if k not in ['WOLTLAB_REF_LINE','WOLTLAB_REFERENCES_ROOT']}
        env['WOLTLAB_REF_LINE']=line
        if explicit is not None:env['WOLTLAB_REFERENCES_ROOT']=str(explicit)
        script='''TOOLS_DIR="$1"; MAIN_DIR="$2"; source "$3"
ONLINE_FIXTURE="$4"
woltlab_detect_online_core() { printf '%s\\thttps://example.invalid/core.zip\\n' "$ONLINE_FIXTURE"; }
SWPM_LOCAL_CORE=old; SWPM_UPDATE_AVAILABLE=1
woltlab_refs_status; rc=$?
printf '%s|%s|%s|%s\\n' "$rc" "$SWPM_LOCAL_CORE" "$SWPM_REF_LINE" "$SWPM_UPDATE_AVAILABLE"
'''
        result=subprocess.run(['bash','-c',script,'fixture',str(tools),str(self.manager),str(TOOLS/'woltlab-refs-lib.sh'),online or line+'.0'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return result.stdout.strip().split('|')

    def test_status_default_line_root_does_not_read_old_manager_core_marker(self):
        tools=self.manager/'tools';tools.mkdir()
        legacy=self.manager/'woltlab-core';legacy.mkdir();(legacy/'.swpm-core-version').write_text('6.2.6')
        selected=self.manager/'.references/6.3/woltlab-core';selected.mkdir(parents=True);(selected/'.swpm-core-version').write_text('6.3.0')
        before=self.fingerprint(self.manager)
        self.assertEqual(self.status('6.3'),['0','6.3.0','6.3','0'])
        self.assertEqual(self.fingerprint(self.manager),before)

    def test_status_explicit_root_stays_exact_and_mixed_lines_are_errors(self):
        default=self.manager/'.references/6.3/woltlab-core';default.mkdir(parents=True);(default/'.swpm-core-version').write_text('6.3.0')
        explicit=self.root/'explicit';(explicit/'woltlab-core').mkdir(parents=True);(explicit/'woltlab-core/.swpm-core-version').write_text('6.3.1')
        self.assertEqual(self.status('6.3',explicit,'6.3.1'),['0','6.3.1','6.3','0'])
        (explicit/'woltlab-core/.swpm-core-version').write_text('6.2.6')
        self.assertEqual(self.status('6.2',explicit,'6.2.6'),['0','6.2.6','6.2','0'])
        self.assertEqual(self.status('6.3',explicit,'6.3.0')[:3],['1','6.2.6','6.3'])

    def test_status_protected_root_error_clears_old_update_claim(self):
        outside=self.root/'outside';outside.mkdir()
        alias=self.root/'alias';alias.symlink_to(outside,target_is_directory=True)
        self.assertEqual(self.status('6.3',alias),['1','','6.3','0'])
        self.assertFalse(list(outside.iterdir()))

    def test_status_and_read_only_updater_choose_the_same_default_root(self):
        selected=self.provision('6.3')
        core=selected/'woltlab-core';core.mkdir();(core/'.swpm-core-version').write_text('6.3.0')
        tools=self.manager/'tools';tools.mkdir()
        for name in ['update-woltlab-version.sh','woltlab-refs-lib.sh','woltlab-reference-selection.py','sync-woltlab-git.py']:
            shutil.copy2(TOOLS/name,tools/name)
        sources=self.root/'local-sources.json';sources.write_text(json.dumps({'sample':str(selected/'woltlab-github')}))
        before=self.fingerprint(self.manager)
        self.assertEqual(self.status('6.3'),['0','6.3.0','6.3','0'])
        env={k:v for k,v in os.environ.items() if k not in ['WOLTLAB_REF_LINE','WOLTLAB_REFERENCES_ROOT']}
        env['WOLTLAB_REFERENCE_SOURCES']=str(sources)
        result=subprocess.run(['bash',str(tools/'update-woltlab-version.sh'),'--check','--refs-only','6.3'],env=env,capture_output=True,text=True)
        self.assertEqual(result.returncode,2,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['references'][0]['path'],str(selected/'sample'))
        self.assertEqual(self.fingerprint(self.manager),before)

    def test_wrong_line_lock_and_core_are_rejected(self):
        package=self.package('6.2.0');selected=self.provision('6.3')
        with self.assertRaisesRegex(ValueError,'lock line'):refs.select(package,root=selected)
        with self.assertRaisesRegex(ValueError,'line/patch'):refs.select(self.package('6.3.0',name='other'),root=selected,core=self.core('6.2.6'))

    def core(self,version):
        core=self.root/('installed-'+version.replace(' ','-'));(core/'lib/system').mkdir(parents=True)
        (core/'lib/system/WCF.class.php').write_text("<?php define('WCF_VERSION', '"+version+"');")
        return core

    def test_patch_minimum_and_exclusion_are_real_compatibility_bounds(self):
        package=self.package('6.2.6');selected=self.provision('6.2','6.2.5')
        with self.assertRaisesRegex(ValueError,'line/patch'):refs.select(package,root=selected)
        self.assertEqual(refs.select(package,root=selected,core=self.core('6.2.6'))['version'],'6.2.6')
        package=self.package('6.2.0',excluded='6.2.6',name='excluded')
        with self.assertRaisesRegex(ValueError,'excluded'):refs.select(package,root=selected,core=self.core('6.2.7'))

    def test_dirty_head_origin_and_symlink_refs_never_supply_build_inputs(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        path=selected/'woltlab-docs/source';path.write_text('local changes')
        with self.assertRaisesRegex(ValueError,'Dirty'):refs.select(package,root=selected)
        self.git(path.parent,'add','.');self.git(path.parent,'commit','-m','local')
        with self.assertRaisesRegex(ValueError,'HEAD'):refs.select(package,root=selected)
        self.git(path.parent,'checkout','HEAD~1')
        path.rename(self.root/'outside');path.symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):refs.select(package,root=selected)

    def test_read_lock_rejects_redirected_git_worktree_before_source_selection(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        checkout=selected/'woltlab-docs';outside=self.root/'outside';outside.mkdir()
        (outside/'source').write_text('reference')
        self.git(checkout,'config','core.worktree',str(outside))
        before=self.fingerprint(selected)
        with self.assertRaisesRegex(ValueError,'worktree boundary'):refs.read_lock(selected,'6.3')
        with self.assertRaisesRegex(ValueError,'worktree boundary'):refs.select(package,root=selected)
        self.assertEqual(self.fingerprint(selected),before)
        self.assertEqual((outside/'source').read_text(),'reference')

    def test_managed_clone_metadata_and_index_cannot_be_redirected(self):
        package=self.package('6.3.0');selected=self.provision('6.3');checkout=selected/'woltlab-docs'
        external=self.root/'foreign-index';external.write_bytes((checkout/'.git/index').read_bytes())
        original=external.read_bytes()
        previous=os.environ.get('GIT_INDEX_FILE')
        try:
            os.environ['GIT_INDEX_FILE']=str(external)
            with self.assertRaisesRegex(ValueError,'index boundary'):refs.select(package,root=selected)
        finally:
            if previous is None:os.environ.pop('GIT_INDEX_FILE',None)
            else:os.environ['GIT_INDEX_FILE']=previous
        self.assertEqual(external.read_bytes(),original)
        self.assertEqual(refs.select(package,root=selected)['line'],'6.3')

    def test_typings_paths_cannot_silently_point_to_another_tree(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        config=package/'tsconfig.json'
        config.write_text(json.dumps({'compilerOptions':{'paths':{'WoltLabSuite/*':['../../old/woltlab-d-ts/WoltLabSuite/*']}}}))
        with self.assertRaisesRegex(ValueError,'compiler input'):refs.select(package,root=selected)
        config.write_text(json.dumps({'compilerOptions':{'paths':{'WoltLabSuite/*':[str(selected/'woltlab-d-ts/WoltLabSuite/*')]}}}))
        self.assertEqual(refs.select(package,root=selected)['line'],'6.3')

    def test_native_wildcard_aliases_and_every_fallback_target_are_checked(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        config=package/'tsconfig.json';typings=selected/'woltlab-d-ts'
        for key in ['WoltLabSuite*','WoltLabSuite/Core*','WoltLab*','*']:
            with self.subTest(alias=key):
                wrong={'compilerOptions':{'baseUrl':'.','paths':{key:['old-types/*']}}}
                config.write_text(json.dumps(wrong))
                with self.assertRaisesRegex(ValueError,'compiler input'):refs.select(package,root=selected)
                wrong['compilerOptions']['paths'][key]=[str(typings/'*'),'old-types/*']
                config.write_text(json.dumps(wrong))
                with self.assertRaisesRegex(ValueError,'compiler input'):refs.select(package,root=selected)
                wrong['compilerOptions']['paths'][key]=[str(typings/'*')]
                config.write_text(json.dumps(wrong))
                self.assertEqual(refs.select(package,root=selected)['line'],'6.3')
        config.write_text(json.dumps({'compilerOptions':{'paths':{'Vendor/*':['vendor/*'],'WoltLabSuiteExtra*':['other/*']}}}))
        self.assertEqual(refs.select(package,root=selected)['line'],'6.3')

    def test_native_alias_target_suffix_traversal_is_not_hidden_by_star_prefix(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        config=package/'tsconfig.json'
        config.write_text(json.dumps({'compilerOptions':{'paths':{'WoltLabSuite*':[str(selected/'woltlab-d-ts/*/../../old-types')]}}}))
        with self.assertRaisesRegex(ValueError,'compiler input'):refs.select(package,root=selected)

    def test_default_root_ancestor_symlink_prevents_actual_zip_write(self):
        outside=self.root/'outside';outside.mkdir()
        (self.manager/'.references').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ancestor symlink'):refs.root_for('6.3',manager=self.manager)
        with self.assertRaisesRegex(ValueError,'ancestor symlink'):
            refs.install_core(self.manager/'.references/6.3','6.3.0',self.archive('6.3.0'),'https://example.invalid/6.3.0')
        self.assertEqual(list(outside.iterdir()),[])
        self.assertFalse((outside/'6.3/woltlab-core/core-lock.json').exists())

    def test_explicit_root_deep_or_broken_ancestor_symlink_is_protected(self):
        outside=self.root/'outside';outside.mkdir()
        alias=self.root/'alias';alias.symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ancestor symlink'):refs.root_for('6.2',alias/'deep/6.2')
        alias.unlink();alias.symlink_to(self.root/'missing',target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'ancestor symlink'):refs.root_for('6.2',alias/'deep/6.2')
        self.assertFalse((self.root/'missing').exists())

    def test_new_regular_default_parent_and_exact_line_are_valid(self):
        self.assertEqual(refs.root_for('6.3',manager=self.manager),self.manager/'.references/6.3')
        self.assertFalse((self.manager/'.references').exists())
        refs.install_core(self.manager/'.references/6.3','6.3.0',self.archive('6.3.0'),'https://example.invalid/6.3.0')
        self.assertEqual(refs.verify_core(self.manager/'.references/6.3')['line'],'6.3')
        with self.assertRaisesRegex(ValueError,'major.minor'):refs.root_for('6.3.0',manager=self.manager)

    def test_missing_and_duplicate_wcf_metadata_do_not_guess(self):
        package=self.package('6.3.0')
        xml=package/'package.xml';source=xml.read_text()
        xml.write_text('<package name="com.vendor.sample"/>')
        with self.assertRaisesRegex(ValueError,'No WCF'):refs.constraints(package)
        xml.write_text(source.replace('</requiredpackages>','<requiredpackage minversion="6.2.0">com.woltlab.wcf</requiredpackage></requiredpackages>'))
        with self.assertRaisesRegex(ValueError,'Duplicate'):refs.constraints(package)

    def test_shell_exports_are_quoted_not_evaluated_package_text(self):
        package=self.package('6.3.0');selected=self.provision('6.3')
        result=subprocess.run(['python3',str(TOOLS/'woltlab-reference-selection.py'),'--package',str(package),'--root',str(selected),'--shell'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('export WOLTLAB_CORE_REFERENCE=',result.stdout)
        self.assertIn('export WOLTLAB_REF_LINE=6.3',result.stdout)

    def test_explicit_family_required_closure_derives_transitive_core(self):
        base=self.package('6.2.6',name='base')
        addon=self.root/'addon';addon.mkdir()
        (addon/'package.xml').write_text('<package name="com.vendor.addon"><packageinformation><version>1.0.0</version></packageinformation><requiredpackages><requiredpackage minversion="1.0.0">com.vendor.base</requiredpackage></requiredpackages></package>')
        manifest=self.root/'family.json';manifest.write_text(json.dumps({'paths':[str(addon),str(base)]}))
        self.assertEqual(refs.constraints(addon,manifest)[0],'6.2.6')
        with self.assertRaisesRegex(ValueError,'No WCF'):refs.constraints(addon)
        other=self.package('6.3.0',name='other')
        with self.assertRaisesRegex(ValueError,'not the explicit family target'):refs.constraints(other,manifest)

    def archive(self,version,name='suite.zip'):
        path=self.root/name;buffer=io.BytesIO()
        with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
            content=("<?php define('WCF_VERSION', '"+version+"');").encode()
            member=tarfile.TarInfo('install/files/lib/system/WCF.class.php');member.size=len(content);tar.addfile(member,io.BytesIO(content))
        with zipfile.ZipFile(path,'w') as zipped:
            zipped.writestr('WCFSetup.tar.gz',buffer.getvalue());zipped.writestr('install.php','<?php');zipped.writestr('test.php','<?php')
        return path

    def test_core_zip_exact_sha_pin_and_read_only_verification(self):
        root=self.manager/'.references/6.2';archive=self.archive('6.2.6')
        info=refs.install_core(root,'6.2.6',archive,'https://example.invalid/woltlab-suite-6.2.6.zip')
        self.assertEqual(info['archive_sha256'],hashlib.sha256(archive.read_bytes()).hexdigest())
        before=self.fingerprint(root)
        self.assertEqual(refs.verify_core(root,'6.2.6'),info)
        self.assertEqual(before,self.fingerprint(root))
        (root/'woltlab-core/test.php').write_text('modified')
        with self.assertRaisesRegex(ValueError,'SHA pin'):refs.verify_core(root)

    def test_core_update_preserves_prior_archive_and_lock_exact_bytes(self):
        root=self.manager/'.references/6.2';archive=self.archive('6.2.6')
        refs.install_core(root,'6.2.6',archive,'https://example.invalid/6.2.6')
        old=self.fingerprint(root/'woltlab-core')
        refs.install_core(root,'6.2.7',self.archive('6.2.7','new.zip'),'https://example.invalid/6.2.7')
        archived=next((root/'history').iterdir())
        self.assertEqual(self.fingerprint(archived),old)
        self.assertEqual(refs.verify_core(root)['version'],'6.2.7')

    def test_wrong_archive_line_and_unowned_core_destination_are_protected(self):
        root=self.manager/'.references/6.3'
        with self.assertRaisesRegex(ValueError,'native WCF_VERSION'):refs.install_core(root,'6.3.0',self.archive('6.2.6'),'https://example.invalid/wrong')
        self.assertFalse(root.exists())
        (root/'woltlab-core').mkdir(parents=True);(root/'woltlab-core/precious').write_text('keep')
        before=self.fingerprint(root)
        with self.assertRaises(OSError):refs.install_core(root,'6.3.0',self.archive('6.3.0','valid.zip'),'https://example.invalid/valid')
        self.assertEqual(before,self.fingerprint(root))

    def test_real_build_and_validator_refuse_wrong_line_before_compilation(self):
        package=self.package('6.2.0');selected=self.provision('6.3')
        before=(package/'package.xml').read_bytes()
        env={**os.environ,'WOLTLAB_REFERENCES_ROOT':str(selected),'DEBUG_LOG_DIR':str(self.root/'logs')}
        for name,args in [('build.sh',[str(package),'same']),('validate-plugin.sh',[str(package)])]:
            result=subprocess.run(['bash',str(TOOLS/name),*args],capture_output=True,text=True,env=env)
            self.assertEqual(result.returncode,1,result.stdout+result.stderr)
            self.assertIn('lock line',result.stderr)
            self.assertEqual((package/'package.xml').read_bytes(),before)
            self.assertFalse((package/'js').exists())


if __name__=='__main__':unittest.main()
