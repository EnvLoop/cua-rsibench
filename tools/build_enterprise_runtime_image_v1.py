"""Build an owned enterprise runner image from tracked public source only.

Private work, shell profiles, Docker credentials, caches and Git state never
enter the staged context. This builds a runner; it does not qualify apps or
dispatch model calls. Qualification fixtures are mounted separately at run time.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
EXTRA=('runtime/enterprise/runner.Dockerfile','tools/build_enterprise_runtime_image_v1.py',
 'magento_catalog_factory/native_quote_navigation_v2.py','magento_catalog_factory/native_queue_runtime_v3.py',
 'magento_catalog_factory/native_surface_workers_v2.py','magento_catalog_factory/native_surface_facade_v2.py',
 'magento_catalog_factory/native_queue_profile_v3.py','magento_catalog_factory/native_surface_budget_performance_v3.py',
 'tests/test_magento_quote_navigation_v2.py')
EXTRA=tuple(dict.fromkeys((*EXTRA,
    *(f'magento_catalog_factory/native_queue_profile_v{version}.py' for version in (4,5)),
    *(f'magento_catalog_factory/native_queue_runtime_v{version}.py' for version in range(4,10)),
    *(f'magento_catalog_factory/native_surface_budget_performance_v{version}.py' for version in range(4,10)),
    *(f'magento_catalog_factory/native_surface_workers_v{version}.py' for version in range(3,10)),
    *(f'magento_catalog_factory/native_surface_facade_v{version}.py' for version in range(3,10)),
    *(f'magento_catalog_factory/native_surface_teacher_v{version}.py' for version in range(2,8)),
    *(f'magento_catalog_factory/native_surface_shared_base_v{version}.py' for version in range(2,8)),
    *(f'magento_catalog_factory/native_surface_actor_v{version}.py' for version in range(2,6)),
    *(f'magento_catalog_factory/native_startup_readiness_v{version}.py' for version in (3,4)),
    *(f'magento_catalog_factory/native_saved_baseline_migration_v{version}.py' for version in (1,2)),
    'magento_catalog_factory/native_reference_bulk_price_v3.py','magento_catalog_factory/native_reference_continuation_v3.py')))
SOURCE_ROOTS={'src','tools','gitlab_world','magento_catalog_factory','enterprise_fallback',
 'native_desktop_factory','ppt_wdi_factory','sec_excel_factory','tests','docs','runtime'}

def public_source(name):
    path=Path(name)
    return (not path.is_absolute() and '..' not in path.parts and
        (name=='pyproject.toml' or path.parts[0] in SOURCE_ROOTS) and
        not any(part in ('work','.git','__pycache__','.venv') or part.endswith('.private') for part in path.parts) and
        not path.name.endswith(('.private.json','.private.py','.private.log','.private.bin')) and
        not path.name.startswith('.env'))

def write(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw)

def stage_context(output):
    output=Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT/'work'):raise ValueError('Fresh owned build namespace required')
    output.mkdir(parents=True,mode=0o700);context=output/'context.private';context.mkdir(mode=0o700)
    tracked=subprocess.run(['git','ls-files','-z'],cwd=ROOT,check=True,capture_output=True).stdout.decode().split('\0')
    names=sorted({name for name in tracked+list(EXTRA) if name and public_source(name)})
    manifest=[]
    for name in names:
        source=ROOT/name
        if source.is_symlink() or not source.is_file():raise ValueError('Nonregular public source in staged context')
        target=context/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        raw=source.read_bytes();target.write_bytes(raw);target.chmod(0o644)
        manifest.append({'path':name,'sha256':sha256(raw).hexdigest(),'size':len(raw)})
    write(output/'context-manifest.private.json',{'schema':'envloop-enterprise-runner-context-v1','source_files':manifest,
        'ignored_work_and_credentials_copied':False,'provider_calls':0,'native_application_calls':0})
    return context

def build(*,output,context,tag):
    if not re.fullmatch(r'envloop-enterprise-runner:[a-z0-9][a-z0-9.-]{1,63}',tag):raise ValueError('Owned runner image tag required')
    staged=stage_context(output);output=Path(output).resolve()
    args=['docker','--context',context,'build','--iidfile',str(output/'image-id.private.txt'),
        '-t',tag,'-f',str(staged/'runtime/enterprise/runner.Dockerfile'),str(staged)]
    write(output/'build-intent.private.json',{'argv':args,'tag':tag,'model_calls':0,'automatic_retries':0})
    result=subprocess.run(args,cwd=ROOT)
    write(output/'build-terminal.private.json',{'exit_code':result.returncode,'model_calls':0,'automatic_retries':0})
    if result.returncode:raise ValueError('Runner build failed; original logs and context retained')
    identity=(output/'image-id.private.txt').read_text().strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',identity):raise ValueError('Actual built image identity missing')
    write(output/'build-result.private.json',{'status':'actual_runner_image_built','tag':tag,'image_id':identity,
        'model_calls':0,'native_application_qualification_performed':False})
    return {'status':'actual_runner_image_built','tag':tag,'image_id':identity}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--context',default='colima-cua-scale')
    parser.add_argument('--tag',required=True)
    print(json.dumps(build(**vars(parser.parse_args())),sort_keys=True))

if __name__=='__main__':main()
