"""Prepare a public-dependency-only E2B controller template; build only with --execute."""
import argparse
import json
from pathlib import Path
import shlex

from run_cloud_chain_remote import runtime_origin
from remote_cloud_worker import VERSION, sha, write_json


def prepare(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    runtime = runtime_origin()
    requirements = '\n'.join(name + '==' + version for name, version in runtime['packages'].items()) + '\n'
    (out / 'runtime-lock.txt').write_text(requirements)
    digest = sha(requirements.encode())
    plan = {'operational_version': VERSION, 'template': 'cua-harbor-remote-' + digest[:12],
            'image': 'python:3.12-slim', 'cpus': 2, 'memory_mb': 4096,
            'requirements_sha256': digest, 'runtime': runtime,
            'private_files_uploaded': False, 'credential_values_in_build': False}
    write_json(out / 'plan.json', plan)
    return plan


def build(out):
    from e2b import Template
    out = Path(out).resolve()
    plan = json.loads((out / 'plan.json').read_text())
    if (out / 'build-intent.json').exists():
        raise ValueError('build was already requested; inspect provider state rather than repeat it')
    if sha((out / 'runtime-lock.txt').read_bytes()) != plan['requirements_sha256']:
        raise ValueError('dependency lock changed')
    if Template.exists(plan['template']):
        write_json(out / 'build-result.json', {'state': 'alias_present', 'readiness_verified': False})
        return {'state': 'alias_present', 'template': plan['template']}
    template = Template(file_context_path=str(out)).from_image(plan['image'])
    template = template.copy('runtime-lock.txt', '/tmp/cua-runtime-lock.txt', user='root')
    template = template.run_cmd(
        'python -m venv /opt/cua && /opt/cua/bin/pip install --no-cache-dir -r /tmp/cua-runtime-lock.txt',
        user='root')
    write_json(out / 'build-intent.json', {'template': plan['template'], 'requirements_sha256': plan['requirements_sha256']})
    result = Template.build(template=template, name=plan['template'], cpu_count=plan['cpus'], memory_mb=plan['memory_mb'])
    record = {'state': 'built_ready', 'template': plan['template'],
              'template_id_sha256': sha(result.template_id.encode()), 'build_id_sha256': sha(result.build_id.encode())}
    write_json(out / 'build-result.json', record)
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        result = build(args.out) if args.execute else prepare(args.out)
        print(json.dumps({'state': result.get('state', 'offline_plan'), 'template': result['template'],
                          'operational_version': VERSION}))
    except Exception as exc:
        print(json.dumps({'state': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
