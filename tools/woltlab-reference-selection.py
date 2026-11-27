#!/usr/bin/env python3
"""Select explicit, package-compatible WoltLab reference lines without fallback."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile

TOOLS = Path(__file__).resolve().parent
MANAGER = TOOLS.parent
REQUIRED = ('woltlab-github', 'woltlab-docs', 'woltlab-d-ts')


def line_of(version):
    match = re.fullmatch(r'(\d+\.\d+)(?:\.\d+(?: (?:dev|Alpha|Beta|RC) \d+)?)?', version)
    if not match:
        raise ValueError('Explicit major.minor or WoltLab package version required')
    return match[1]


def version_key(version):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?: (dev|Alpha|Beta|RC) (\d+))?', version)
    if not match:
        raise ValueError('Invalid WoltLab version in compatibility metadata')
    return (*map(int, match.group(1, 2, 3)), {'dev':0, 'Alpha':1, 'Beta':2, 'RC':3, None:4}[match[4]], int(match[5] or 0))


def package_xml(path):
    path = Path(path)
    for candidate in ([path] if path.is_file() else [path/'temp_edit/package.xml', path/'package.xml']):
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError('Selected package has no package.xml')


def constraints(package, manifest=None):
    xml = package_xml(package)
    roots = [ET.parse(xml).getroot()]
    if manifest:
        # Reuse the existing explicit family resolver, including required-only closure.
        spec = importlib.util.spec_from_file_location('swpm_family_refs', TOOLS/'check-family-deps.py')
        family = importlib.util.module_from_spec(spec); spec.loader.exec_module(family)
        graph, errors = family.build_family(Path(manifest).resolve())
        if errors:
            raise ValueError('Invalid explicit family manifest: ' + '; '.join(errors))
        packages = {p['id']:p for p in graph['packages']}
        identifier = roots[0].get('name')
        if identifier not in packages or Path(packages[identifier]['path']).resolve() != xml.parent.resolve():
            # A temp_edit layout records the outer root, not the XML directory.
            if identifier not in packages or package_xml(packages[identifier]['path']) != xml:
                raise ValueError('Selected package is not the explicit family target')
        visited = set()
        def visit(pid):
            if pid in visited: return
            visited.add(pid)
            meta = packages[pid]
            for dep, _ in meta['requires']:
                if dep in packages: visit(dep)
            if pid != identifier: roots.append(ET.parse(package_xml(meta['path'])).getroot())
        visit(identifier)
    minimums, exclusions = [], []
    for root in roots:
        found = 0
        for parent in root:
            kind = parent.tag.rsplit('}', 1)[-1]
            for node in parent:
                if (node.text or '').strip() != 'com.woltlab.wcf': continue
                if kind == 'requiredpackages' and node.tag.rsplit('}', 1)[-1] == 'requiredpackage':
                    found += 1
                    value = node.get('minversion', '')
                    version_key(value); minimums.append(value)
                elif kind == 'excludedpackages' and node.tag.rsplit('}', 1)[-1] == 'excludedpackage':
                    value = node.get('version', '')
                    if value != '*': version_key(value)
                    exclusions.append(value)
        if found > 1: raise ValueError('Duplicate WCF compatibility requirement')
    if not minimums:
        raise ValueError('No WCF minimum; supply the explicit required-package family manifest')
    return max(minimums, key=version_key), exclusions


def root_for(line, explicit=None, manager=MANAGER):
    if not re.fullmatch(r'\d+\.\d+',line):
        raise ValueError('Target line must be major.minor')
    selected = Path(explicit) if explicit else Path(manager)/'.references'/line
    return guard_root(selected)


def guard_root(path):
    """Do not follow existing or broken links anywhere in a reference root."""
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path,*path.parents)):
        raise ValueError('Reference root or ancestor symlink is protected; use its explicit canonical path')
    return path


def git(path, *args):
    result = subprocess.run(['git','-C',str(path),*args], capture_output=True,text=True,
        env={**os.environ,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0'},timeout=60)
    if result.returncode: raise ValueError('Cannot verify selected reference Git identity')
    return result.stdout.strip()


def git_boundary(path):
    """Managed references are standalone clones, never redirected worktrees."""
    path = guard_root(path)
    directory = path/'.git'
    guard_root(directory)
    if not directory.is_dir():
        raise ValueError('Managed reference requires its own .git directory')
    # Fetch/checkout also write refs, logs, FETCH_HEAD, packed-refs and locks.
    # Checking only the top-level gitdir would miss redirected descendants.
    for item in directory.rglob('*'):
        if item.is_symlink():
            raise ValueError('Managed reference Git metadata symlink is protected')
        if item.is_file() and item.stat().st_nlink > 1 and item.relative_to(directory).parts[0] != 'objects':
            raise ValueError('Managed reference mutable Git metadata hardlink is protected')
    if Path(git(path,'rev-parse','--show-toplevel')).resolve() != path.resolve():
        raise ValueError('Reference Git worktree boundary differs from selected path')
    actual = Path(git(path,'rev-parse','--absolute-git-dir')).resolve()
    common = Path(git(path,'rev-parse','--git-common-dir'))
    common = (common if common.is_absolute() else path/common).resolve()
    if actual != directory.resolve() or common != directory.resolve():
        raise ValueError('Reference Git metadata boundary differs from its managed clone')
    for name in ('index','objects'):
        expected = guard_root(directory/name)
        location = Path(git(path,'rev-parse','--git-path',name))
        location = (location if location.is_absolute() else path/location).resolve()
        if location != expected.resolve():
            raise ValueError('Reference Git '+name+' boundary differs from its managed clone')
    return path


def read_lock(root, line):
    path = root/'reference-lock.json'
    if path.is_symlink(): raise ValueError('Reference lock symlink is protected')
    data = json.loads(path.read_text())
    if data.get('line') != line or data.get('schema') != 1:
        raise ValueError('Reference lock line/schema differs from selected target')
    rows = data.get('references')
    if not isinstance(rows,list): raise ValueError('Malformed reference lock')
    found = {}
    for row in rows:
        name = row.get('name', '')
        if not re.fullmatch(r'[a-zA-Z0-9_-]+',name) or name in found:
            raise ValueError('Invalid/duplicate pinned reference name')
        path = root/name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Reference path symlink/escape is protected')
        git_boundary(path)
        if row.get('branch') != line or not re.fullmatch(r'[a-f0-9]{40,64}',row.get('local_commit','')):
            raise ValueError('Reference has no exact selected-line commit pin')
        if Path(row.get('path','')).resolve() != path.resolve():
            raise ValueError('Pinned reference path differs from selected root')
        if git(path,'rev-parse','HEAD') != row['local_commit']:
            raise ValueError('Reference HEAD differs from pinned commit')
        if git(path,'status','--porcelain=v1','--untracked-files=all'):
            raise ValueError('Dirty reference is protected')
        if git(path,'remote','get-url','origin').rstrip('/').removesuffix('.git') != str(row.get('url','')).rstrip('/').removesuffix('.git'):
            raise ValueError('Reference origin differs from lock')
        found[name] = row
    if not set(REQUIRED) <= found.keys():
        raise ValueError('Selected lock must pin WCF, documentation and typings')
    return data


def core_version(core):
    source = Path(core)/'lib/system/WCF.class.php'
    match = re.search(r"define\s*\(\s*['\"]WCF_VERSION['\"]\s*,\s*['\"]([^'\"]+)",source.read_text())
    if not match: raise ValueError('Selected Core has no native WCF_VERSION')
    version_key(match[1])
    return match[1]


def check_typings(config, typings):
    """Refuse old compiler paths; never rewrite a user's tsconfig or product."""
    config = Path(config).resolve()
    data = json.loads(config.read_text())
    if data.get('extends'):
        raise ValueError('Inherited tsconfig requires explicit flattened compiler inputs for reference verification')
    options = data.get('compilerOptions', {})
    base = config.parent / options.get('baseUrl', '.')
    paths = options.get('paths', {})
    candidates = []
    for key, values in paths.items():
        if not isinstance(key,str) or key.count('*') > 1:
            raise ValueError('Invalid TypeScript path alias pattern')
        prefix = key.split('*',1)[0]
        native = (key == 'WoltLabSuite' or key.startswith('WoltLabSuite/')
            or ('*' in key and ('WoltLabSuite/'.startswith(prefix) or prefix.startswith('WoltLabSuite/'))))
        if native:
            if not isinstance(values,list) or not values or any(not isinstance(value,str) or not value or value.count('*') > 1 for value in values):
                raise ValueError('Native TypeScript path aliases require explicit nonempty target lists')
            candidates.extend((base, value) for value in values)
    for field in ('include','files'):
        candidates.extend((config.parent, value) for value in data.get(field, []) if 'woltlab-d-ts' in value)
    candidates.extend((base, value) for value in options.get('typeRoots', []) if 'woltlab-d-ts' in value)
    for directory, value in candidates:
        # Keep suffix/traversal segments: checking only the prefix before '*'
        # would miss targets such as pinned/*/../../old-types.
        resolved = (directory / value.replace('*','__swpm_reference_wildcard__')).resolve()
        if not resolved.is_relative_to(Path(typings).resolve()):
            raise ValueError('TypeScript compiler input differs from selected pinned typings; update explicit tsconfig paths')


def select(package, root=None, line=None, core=None, manifest=None, manager=MANAGER):
    minimum, exclusions = constraints(package, manifest)
    line = line or line_of(minimum)
    if not re.fullmatch(r'\d+\.\d+',line): raise ValueError('Target line must be major.minor')
    root = root_for(line,root,manager)
    lock = read_lock(root,line)
    core = Path(core).resolve() if core else root/'woltlab-github/wcfsetup/install/files'
    version = core_version(core)
    if line_of(version) != line or version_key(version) < version_key(minimum):
        raise ValueError('Selected Core line/patch is incompatible with package WCF minimum')
    if any(v == '*' or version_key(version) >= version_key(v) for v in exclusions):
        raise ValueError('Selected Core is excluded by package compatibility')
    xml = package_xml(package)
    config = xml.parent/'tsconfig.json'
    if not config.exists() and xml.parent.name == 'temp_edit':
        config = xml.parent.parent/'tsconfig.json'
    if config.exists(): check_typings(config,root/'woltlab-d-ts')
    return dict(line=line,minimum=minimum,version=version,root=str(root),core=str(core),
        typings=str(root/'woltlab-d-ts'),docs=str(root/'woltlab-docs'),
        lock_sha256=hashlib.sha256((root/'reference-lock.json').read_bytes()).hexdigest(),
        commits={r['name']:r['local_commit'] for r in lock['references']})


def install_core(root, version, archive, url):
    """Atomically provision exact release setup files; never replace unknown content."""
    line = line_of(version)
    if not re.fullmatch(r'\d+\.\d+\.\d+', version): raise ValueError('Exact stable Core release required')
    root = root_for(line,root)
    lock = root/'reference-lock.json'
    if lock.is_symlink(): raise ValueError('Reference lock symlink is protected')
    if lock.exists() and json.loads(lock.read_text()).get('line') != line:
        raise ValueError('Core and reference lock lines conflict')
    destination = root/'woltlab-core'
    previous = None
    if destination.exists() or destination.is_symlink():
        previous = verify_core(root)
        if previous['line'] != line:
            raise ValueError('Existing Core belongs to another line')
        if previous['version'] == version and previous['archive_sha256'] != hashlib.sha256(Path(archive).read_bytes()).hexdigest():
            raise ValueError('Different bytes for an existing pinned Core release')
        if previous['version'] == version: return previous
    history = root/'history'
    if history.is_symlink() or (history.exists() and not history.is_dir()):
        raise ValueError('Core history path is protected')
    with zipfile.ZipFile(archive) as zipped:
        matches = [n for n in zipped.namelist() if Path(n).name == 'WCFSetup.tar.gz']
        if len(matches) != 1: raise ValueError('Core ZIP requires exactly one WCFSetup.tar.gz')
        prefix = str(Path(matches[0]).parent)
        prefix = '' if prefix == '.' else prefix+'/'
        setup = zipped.read(matches[0])
        with tarfile.open(fileobj=io.BytesIO(setup),mode='r:gz') as tar:
            member = tar.getmember('install/files/lib/system/WCF.class.php')
            stream = tar.extractfile(member)
            if not stream or not member.isfile(): raise ValueError('Core archive has no native WCF identity')
            text = stream.read().decode()
        if not re.search(r"define\s*\(\s*['\"]WCF_VERSION['\"]\s*,\s*['\"]"+re.escape(version)+r"['\"]",text):
            raise ValueError('Core archive native WCF_VERSION differs from requested release')
        files = {'WCFSetup.tar.gz':setup}
        for name in ('install.php','test.php'):
            files[name] = zipped.read(prefix+name)
    guard_root(root)
    root.mkdir(parents=True,exist_ok=True)
    guard_root(root)
    stage = Path(tempfile.mkdtemp(prefix='.core-',dir=root))
    try:
        for name,content in files.items(): (stage/name).write_bytes(content)
        shutil.copyfile(archive,stage/f'woltlab-suite-{version}.zip')
        info = dict(schema=1,line=line,version=version,url=url,archive=f'woltlab-suite-{version}.zip',
            archive_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
            files={name:hashlib.sha256(value).hexdigest() for name,value in files.items()})
        (stage/'.swpm-core-version').write_text(version+'\n')
        (stage/'core-lock.json').write_text(json.dumps(info,indent=2)+'\n')
        if previous:
            if verify_core(root) != previous: raise ValueError('Core changed during provisioning')
            history.mkdir(exist_ok=True)
            archived = history/('core-'+previous['version']+'-'+uuid.uuid4().hex)
            destination.rename(archived)
            try:
                stage.rename(destination)
            except BaseException:
                if not destination.exists(): archived.rename(destination)
                raise
        else:
            if destination.exists() or destination.is_symlink(): raise ValueError('Core destination appeared during provisioning')
            stage.rename(destination)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return info


def verify_core(root, wanted=None):
    path = guard_root(root)/'woltlab-core'
    if path.is_symlink() or (path/'core-lock.json').is_symlink(): raise ValueError('Core symlink is protected')
    data = json.loads((path/'core-lock.json').read_text())
    if data.get('schema') != 1 or line_of(data['version']) != data.get('line') or (wanted and data['version'] != wanted):
        raise ValueError('Core release lock differs from requested version/line')
    if (path/'.swpm-core-version').read_text().strip() != data['version']:
        raise ValueError('Core version marker differs from pinned release')
    expected = {data['archive']:data['archive_sha256'], **data['files']}
    if set(data['files']) != {'WCFSetup.tar.gz','install.php','test.php'}: raise ValueError('Incomplete Core files lock')
    for name,sha in expected.items():
        file = path/name
        if Path(name).name != name or file.is_symlink() or hashlib.sha256(file.read_bytes()).hexdigest() != sha:
            raise ValueError('Core file/archive differs from exact SHA pin')
    return data


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path);parser.add_argument('--root',type=Path)
    parser.add_argument('--line');parser.add_argument('--core',type=Path);parser.add_argument('--manifest',type=Path)
    parser.add_argument('--shell',action='store_true');parser.add_argument('--root-only',action='store_true')
    parser.add_argument('--target-line',action='store_true')
    parser.add_argument('--install-core');parser.add_argument('--archive',type=Path);parser.add_argument('--url')
    parser.add_argument('--check-core',action='store_true');parser.add_argument('--version')
    args=parser.parse_args()
    if args.target_line:
        if not args.package:parser.error('target-line requires package')
        print(line_of(constraints(args.package,args.manifest)[0]));return 0
    if args.install_core:
        if not args.root or not args.archive or not args.url:parser.error('install-core requires root/archive/url')
        result=install_core(args.root,args.install_core,args.archive,args.url)
    elif args.check_core:
        if not args.root:parser.error('check-core requires root')
        result=verify_core(args.root,args.version)
    elif args.root_only:
        if not args.line:parser.error('root-only requires explicit line')
        print(root_for(args.line,args.root));return 0
    else:
        if not args.package:parser.error('explicit package required')
        result=select(args.package,args.root,args.line,args.core,args.manifest)
        if args.shell:
            for key,value in [('WOLTLAB_REF_LINE',result['line']),('WOLTLAB_REFERENCES_ROOT',result['root']),
                ('WOLTLAB_CORE_REFERENCE',result['core']),('WOLTLAB_DTS_DIR',result['typings']),('WOLTLAB_DOCS_DIR',result['docs'])]:
                print('export '+key+'='+shlex.quote(value))
            return 0
    print(json.dumps(result,indent=2));return 0


if __name__ == '__main__':
    try:sys.exit(main())
    except (ValueError,OSError,ET.ParseError,KeyError,tarfile.TarError,zipfile.BadZipFile,subprocess.TimeoutExpired) as error:
        print('Reference selection failed: '+str(error),file=sys.stderr);sys.exit(1)
