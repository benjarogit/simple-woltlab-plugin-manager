#!/usr/bin/env python3
"""Check/sync explicit WoltLab branches without resetting local work."""
import argparse
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import tempfile
import uuid
from functools import lru_cache

SOURCES = {
    "woltlab-github": "https://github.com/WoltLab/WCF",
    "woltlab-docs": "https://github.com/WoltLab/docs.woltlab.com",
    "woltlab-d-ts": "https://github.com/WoltLab/d.ts",
    "woltlab-exporter": "https://github.com/WoltLab/com.woltlab.wcf.exporter",
    "woltlab-conversation": "https://github.com/WoltLab/com.woltlab.wcf.conversation",
    "woltlab-legal-notice": "https://github.com/WoltLab/com.woltlab.wcf.legalNotice",
}


def git(*args, cwd=None):
    result = subprocess.run(["git", *map(str, args)], cwd=cwd, capture_output=True, text=True,
                            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"}, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git failed ({result.returncode})")
    return result.stdout.strip()


def normalized(url):
    return url.rstrip("/").removesuffix(".git")


@lru_cache(maxsize=1)
def selection_contract():
    return runpy.run_path(str(Path(__file__).with_name('woltlab-reference-selection.py')))


def git_boundary(path):
    return selection_contract()['git_boundary'](path)


def inspect(root, line, sources):
    # Share the selector's ancestor guard, including direct sync invocations.
    selection = selection_contract()
    root = selection['root_for'](line,root)
    if (root/'history').is_symlink():
        raise ValueError('Reference history symlink is protected')
    lock = root / 'reference-lock.json'
    if lock.is_symlink() or (lock.exists() and (json.loads(lock.read_text()).get('line') != line
            or json.loads(lock.read_text()).get('schema') != 1)):
        raise ValueError('Existing reference lock belongs to another line; choose an isolated root')
    rows = []
    for name, url in sources.items():
        row = {"name": name, "url": url, "branch": line, "path": str(root / name)}
        try:
            if not re.fullmatch(r"[a-zA-Z0-9_-]+", name):
                raise ValueError("Invalid reference directory name")
            remote = git("ls-remote", "--exit-code", "--heads", url, f"refs/heads/{line}")
            row["remote_commit"] = remote.split()[0]
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('Reference symlink/escape is protected')
            if path.exists():
                if not (path / ".git").exists():
                    raise ValueError("Existing non-Git directory is protected")
                git_boundary(path)
                if normalized(git("remote", "get-url", "origin", cwd=path)) != normalized(url):
                    raise ValueError("Origin differs from the configured source")
                # No fetch, config, checkout, cache or lock writes in check mode.
                if git("status", "--porcelain=v1", "--untracked-files=all", cwd=path):
                    raise ValueError("Local changes/untracked files are protected")
                if git('rev-list', 'HEAD', '--not', '--remotes', cwd=path):
                    raise ValueError('Local commits are protected (not reachable from a remote tracking ref)')
                row["local_commit"] = git("rev-parse", "HEAD", cwd=path)
                row["status"] = "current" if row["local_commit"] == row["remote_commit"] else "update"
            else:
                if path.is_symlink():
                    raise ValueError("Broken reference symlink is protected")
                row["status"] = "missing"
        except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            row.update(status="error", error=str(error))
        rows.append(row)
    return rows


def synchronize(root, line, rows):
    # Preflight every source before touching any checkout.
    if any(row["status"] == "error" for row in rows):
        return False
    root = selection_contract()['root_for'](line,root)
    for row in rows:
        try:
            path = Path(row['path'])
            if (not re.fullmatch(r'[a-zA-Z0-9_-]+',row['name'])
                    or path.absolute() != (root/row['name']).absolute()
                    or not path.resolve().is_relative_to(root.resolve())):
                raise ValueError('Reference path differs from selected root')
            if row['status'] != 'missing': git_boundary(path)
        except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as error:
            row.update(status='error',error=str(error))
    if any(row['status'] == 'error' for row in rows): return False
    # Fetch and establish ancestry for every existing checkout before moving any
    # HEAD. A later force-push/divergence must not partially advance other HEADs.
    for row in rows:
        if row['status'] != 'update':
            continue
        path = Path(row['path'])
        try:
            git_boundary(path)
            git('fetch', '--no-tags', 'origin', f'refs/heads/{line}:refs/remotes/origin/{line}', cwd=path)
            git_boundary(path)
            git('fetch', '--no-tags', 'origin', row['remote_commit'], cwd=path)
            git('merge-base', '--is-ancestor', row['local_commit'], row['remote_commit'], cwd=path)
        except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            row.update(status='error', error=str(error))
    if any(row['status'] == 'error' for row in rows):
        return False
    for row in rows:
        path = Path(row["path"])
        try:
            if row["status"] == "current":
                continue
            target = row["remote_commit"]
            if row["status"] == "missing":
                root.mkdir(parents=True, exist_ok=True)
                staging = Path(tempfile.mkdtemp(prefix=f".{row['name']}-", dir=root))
                try:
                    git("clone", "--depth", "1", "--single-branch", "--branch", line,
                        "--no-checkout", row["url"], staging)
                    git_boundary(staging)
                    git("fetch", "--no-tags", "origin", target, cwd=staging)
                    git_boundary(staging)
                    git("checkout", "--detach", target, cwd=staging)
                    if path.exists() or path.is_symlink():
                        raise ValueError("Reference destination appeared during synchronization")
                    staging.rename(path)
                finally:
                    if staging.exists():
                        shutil.rmtree(staging)
            else:
                # Preserve local commits, not just uncommitted files.
                git("merge-base", "--is-ancestor", row["local_commit"], target, cwd=path)
                if git("status", "--porcelain=v1", "--untracked-files=all", cwd=path):
                    raise ValueError("Local work appeared during synchronization")
                if git("rev-parse", "HEAD", cwd=path) != row["local_commit"]:
                    raise ValueError("Local HEAD changed during synchronization")
                git_boundary(path)
                git("checkout", "--detach", target, cwd=path)
            git_boundary(path)
            row.update(status="current", local_commit=git("rev-parse", "HEAD", cwd=path))
        except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            row.update(status="error", error=str(error))
    if any(row["status"] == "error" for row in rows):
        return False
    for row in rows:
        try: git_boundary(Path(row['path']))
        except (RuntimeError,ValueError,OSError,subprocess.TimeoutExpired) as error:
            row.update(status='error',error=str(error))
    if any(row['status'] == 'error' for row in rows): return False
    lock = root / "reference-lock.json"
    content = (json.dumps({"schema": 1, "line": line, "references": rows}, indent=2) + "\n").encode()
    if lock.is_symlink():
        raise ValueError('Reference lock symlink is protected')
    if lock.exists() and lock.read_bytes() == content:
        return True
    history = root / 'history'
    if history.is_symlink():
        raise ValueError('Reference history symlink is protected')
    if lock.exists():
        history.mkdir(exist_ok=True)
        with (history / ('reference-lock-' + uuid.uuid4().hex + '.json')).open('xb') as stream:
            stream.write(lock.read_bytes())
    handle, temporary = tempfile.mkstemp(prefix='.reference-lock-',dir=root)
    try:
        with os.fdopen(handle,'wb') as stream:
            stream.write(content); stream.flush(); os.fsync(stream.fileno())
        Path(temporary).replace(lock)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--line", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--sources", type=Path, help="Optional JSON object of directory names and source URLs")
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+\.[0-9]+", args.line):
        parser.error("line must be major.minor")
    sources = json.loads(args.sources.read_text()) if args.sources else SOURCES
    if not isinstance(sources, dict) or not sources:
        parser.error("sources must be a nonempty JSON object")
    if any(not isinstance(name,str) or not isinstance(url,str) or not url for name,url in sources.items()):
        parser.error('sources must map directory names to nonempty URL strings')
    rows = inspect(args.root.absolute(), args.line, sources)
    success = not any(row["status"] == "error" for row in rows)
    if not args.check:
        success = synchronize(args.root.absolute(), args.line, rows)
    print(json.dumps({"line": args.line, "check_only": args.check, "references": rows}, indent=2))
    if not success:
        return 1
    return 2 if args.check and any(row["status"] != "current" for row in rows) else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(str(error),file=__import__('sys').stderr)
        raise SystemExit(1)
