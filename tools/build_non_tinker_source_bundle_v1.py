"""Deterministic source-layout distribution; no provider, secrets or hidden state.

This packages implementation and exposed development fixtures, never the
private 20/20/100 task allocation, application account, gold or model weights.
The runner operates from the original checkout layout to retain source hashes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import gzip
import io

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ('src', 'tools', 'gitlab_world', 'magento_catalog_factory',
    'native_desktop_factory', 'ppt_wdi_factory', 'sec_excel_factory',
    'enterprise_fallback', 'runtime', 'datasets', 'benchmarks')
EXTRA_FILES = ('pyproject.toml', 'README.md')
DEPLOY_ROOT = 'deployment/non-tinker-runner'
MANIFEST = 'non-tinker-source-manifest.json'
SECRET = re.compile(rb'(?<![A-Za-z0-9_])(?:sk-|tml-)[A-Za-z0-9_-]{24,}|'
    rb'(?<![A-Za-z0-9_])e2b_[a-f0-9]{32,}|'
    rb'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]{48,}-----END')


def digest(raw): return hashlib.sha256(raw).hexdigest()


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        return False
    if any(part.startswith('.env') or '.private' in part or part in
           ('private', '__pycache__', '.git', '.venv', 'node_modules') for part in path.parts):
        return False
    if path.name == '.DS_Store': return False
    return (path.parts[0] in SOURCE_ROOTS or name in EXTRA_FILES
            or name.startswith(DEPLOY_ROOT+'/'))


def checked_file(root, name):
    if not allowed(name): raise ValueError('unsafe_or_private_bundle_member')
    path = Path(root)/name
    # No symlink may smuggle local state, including links on parent components.
    current = Path(root)
    for part in PurePosixPath(name).parts:
        current = current/part
        if current.is_symlink(): raise ValueError('bundle_symlink_forbidden')
    if not path.is_file(): raise ValueError('bundle_member_missing')
    raw = path.read_bytes()
    if SECRET.search(raw): raise ValueError('credential_value_in_bundle_member')
    return raw


def source_names(root, extra=()):
    names = subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
    names = {name for name in names if name and allowed(name)}
    for name in extra:
        if not allowed(name): raise ValueError('unapproved_additional_bundle_file')
        names.add(name)
    # New distribution code is intentionally included before its first commit.
    for name in ('tools/build_non_tinker_source_bundle_v1.py', 'tools/non_tinker_runner_smoke_v1.py'):
        if (Path(root)/name).is_file(): names.add(name)
    for path in (Path(root)/DEPLOY_ROOT).rglob('*'):
        if path.is_file(): names.add(path.relative_to(root).as_posix())
    return sorted(names)


def stage(root, output, extra=()):
    root, output = Path(root).resolve(), Path(output)
    if output.exists() or output.is_symlink(): raise ValueError('fresh_build_context_required')
    # Validate every input before creating the output.
    contents = [(name, checked_file(root,name)) for name in source_names(root,extra)]
    if not contents: raise ValueError('empty_source_bundle')
    manifest = {'schema':'envloop-non-tinker-source-bundle-v1',
        'scope':'implementation_and_public_development_fixtures',
        'training_provider_required_for_build':False, 'contains_private_task_allocation':False,
        'benchmark_model_results_claimed':False,
        'files':[{'path':name,'sha256':digest(raw),'size':len(raw)} for name,raw in contents]}
    output.mkdir(parents=True,mode=0o700)
    for name,raw in contents:
        path = output/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw);path.chmod(0o644)
    (output/MANIFEST).write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    # Docker consumes this file at the build-context root.
    shutil.copyfile(output/DEPLOY_ROOT/'.dockerignore',output/'.dockerignore')
    verify(output)
    return manifest


def verify(root):
    root = Path(root)
    value = json.loads((root/MANIFEST).read_bytes())
    if value['schema'] != 'envloop-non-tinker-source-bundle-v1': raise ValueError('bundle_schema_changed')
    rows=value['files'];names=[row['path'] for row in rows]
    if len(names)!=len(set(names)): raise ValueError('duplicate_bundle_member')
    for row in rows:
        raw=checked_file(root,row['path'])
        if len(raw)!=row['size'] or digest(raw)!=row['sha256']: raise ValueError('bundle_member_changed')
    actual={path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()}
    if actual != set(names)|{MANIFEST,'.dockerignore'}: raise ValueError('unlisted_bundle_member')
    if (root/'.dockerignore').read_bytes() != (root/DEPLOY_ROOT/'.dockerignore').read_bytes():
        raise ValueError('build_exclusion_policy_changed')
    return value


def archive(context, target):
    context,target=Path(context),Path(target)
    verify(context)
    if target.exists() or target.is_symlink(): raise ValueError('fresh_source_archive_required')
    with target.open('xb') as stream, gzip.GzipFile(fileobj=stream,mode='wb',filename='',mtime=0) as zipped:
        with tarfile.open(fileobj=zipped,mode='w') as tar:
            for path in sorted(context.rglob('*')):
                if not path.is_file():continue
                raw=path.read_bytes();info=tarfile.TarInfo(path.relative_to(context).as_posix())
                info.size=len(raw);info.mode=0o644;info.mtime=0;info.uid=info.gid=0
                tar.addfile(info,io.BytesIO(raw))
    return {'archive_sha256':digest(target.read_bytes()),'file_count':len(verify(context)['files'])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('stage');p.add_argument('--root',default=str(ROOT));p.add_argument('--out',required=True)
    p.add_argument('--include',action='append',default=[]);p.add_argument('--archive')
    p=sub.add_parser('verify');p.add_argument('--root',required=True)
    args=parser.parse_args()
    if args.command=='verify':value=verify(args.root);print(json.dumps({'verified_files':len(value['files'])}));return
    value=stage(args.root,args.out,args.include)
    result={'staged_files':len(value['files']),'benchmark_results_claimed':False}
    if args.archive:result.update(archive(args.out,args.archive))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
