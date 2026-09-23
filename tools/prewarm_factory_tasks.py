"""Serially prepare Harbor's exact E2B task templates, without running agents.

Default mode is an offline plan. --execute checks cached aliases and builds
only missing ones, with the public E2B template API. Never calls env.start(),
creates a sandbox, force-rebuilds an alias, or invokes a model. Run before any
Harbor jobs for these same task packages; unmodified Harbor does not honor this
tool's local process lock.
"""
import argparse
import asyncio
import fcntl
import hashlib
import importlib.metadata
import inspect
import json
import os
import re
import time
from pathlib import Path

from cursibench.factory_final import read, sha, validate_study
from cursibench.factory_provenance import validate_selection_packages

ROOT = Path(__file__).resolve().parents[1]


def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(path)


def make_plan(study, researcher='astra', scope='final'):
    """Pure local inspection; does not require provider credentials."""
    from harbor.environments.e2b import E2BEnvironment
    from harbor.models.task.task import Task
    from harbor.models.task.verifier_mode import resolve_effective_verifier_env_config
    from harbor.models.trial.paths import TrialPaths

    if not re.fullmatch(r'[a-z][a-z0-9]*', researcher):
        raise ValueError('invalid campaign alias')
    if scope not in ('selection', 'final', 'all'):
        raise ValueError('invalid task scope')
    study = Path(study).resolve()
    state = read(study / (researcher + '-campaign.json'))
    packages = []
    if scope in ('selection', 'all'):
        proof = validate_selection_packages(ROOT, study, state)
        packages.extend((study / 'selection' / task, task_hash)
                        for task, task_hash in proof['task_package_hashes'].items())
    if scope in ('final', 'all'):
        proof = validate_study(ROOT, study, state)
        for chunk, tasks in proof['chunks'].items():
            packages.extend((study / 'sealed-final' / chunk / task,
                             proof['task_package_hashes'][task]) for task in tasks)

    entries = []
    for package, package_hash in sorted(packages):
        task = Task(package)
        if task.has_steps:
            raise ValueError('this tool supports the fixed single-step factory tasks only')
        verifier_config = resolve_effective_verifier_env_config(task.config, None)
        if verifier_config is None:
            raise ValueError('factory tasks require a separate verifier')
        for role, context, config in (
                ('agent', task.paths.environment_dir, task.config.environment),
                ('verifier', task.paths.tests_dir, verifier_config)):
            # Constructor is local. It derives exactly the alias/resource values
            # used by installed Harbor; no private build/start method is called.
            environment = E2BEnvironment(
                environment_dir=context, environment_name=task.short_name,
                session_id='factory-prewarm-plan',
                trial_paths=TrialPaths(trial_dir=study / 'prewarm-local-path-unused'),
                task_env_config=config)
            entries.append({'task': task.short_name, 'role': role,
                            'alias': environment._template_name,
                            'environment_id': environment.environment_id,
                            'environment_dir': str(context),
                            'docker_image': config.docker_image,
                            'cpus': environment._effective_cpus,
                            'memory_mb': environment._effective_memory_mb,
                            'build_timeout_seconds': config.build_timeout_sec,
                            'task_package_sha256': package_hash})
    aliases = [entry['alias'] for entry in entries]
    if len(aliases) != len(set(aliases)):
        raise ValueError('duplicate template alias in bounded preparation plan')
    return {'study': str(study), 'researcher': researcher, 'scope': scope,
            'protocol_hash': state['protocol_hash'], 'entries': entries,
            'packages': len(packages), 'model_calls': 0, 'sandbox_creations': 0,
            'versions': {name: importlib.metadata.version(name) for name in ('harbor', 'e2b')},
            'harbor_e2b_source_sha256': sha(inspect.getfile(E2BEnvironment)),
            'cache_policy': 'skip existing aliases; await each missing build before continuing',
            'cached_readiness_boundary': 'alias existence is not an independent READY-state check'}


async def execute(plan, out):
    from e2b import AsyncTemplate, Template

    if not os.environ.get('E2B_API_KEY'):
        raise ValueError('E2B_API_KEY is required for execution')
    # A common repo-level lock prevents two invocations of this tool racing.
    # It cannot serialize the separately installed, unmodified Harbor launcher.
    lock_path = ROOT / 'work/e2b-template-prewarm.lock'
    lock_path.parent.mkdir(exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if make_plan(plan['study'], plan['researcher'], plan['scope']) != plan:
            raise ValueError('task packages/runtime changed after planning')
        out = Path(out).resolve()
        out.mkdir(parents=True, exist_ok=False)
        save(out / 'plan.json', plan)
        result = {'started_at': time.time(), 'complete': False, 'entries': [],
                  'model_calls': 0, 'sandbox_creations': 0}
        save(out / 'result.json', result)
        try:
            for entry in plan['entries']:
                if make_plan(plan['study'], plan['researcher'], plan['scope']) != plan:
                    raise ValueError('task packages/runtime changed during preparation')
                row = {'task': entry['task'], 'role': entry['role'],
                       'alias': entry['alias'], 'started_at': time.time(), 'status': 'checking'}
                result['entries'].append(row)
                save(out / 'result.json', result)
                # Do not rebuild existing shared aliases, even if one could be
                # building elsewhere. Complete this barrier before starting jobs.
                if await AsyncTemplate.exists(entry['alias']):
                    row.update(status='cache_present', readiness_verified=False)
                else:
                    row['status'] = 'building'
                    save(out / 'result.json', result)
                    if entry['docker_image']:
                        template = Template().from_image(image=entry['docker_image'])
                    else:
                        template = Template(file_context_path=entry['environment_dir']).from_dockerfile(
                            dockerfile_content_or_path=str(Path(entry['environment_dir']) / 'Dockerfile'))
                    resources = {}
                    if entry['cpus'] is not None:
                        resources['cpu_count'] = entry['cpus']
                    if entry['memory_mb'] is not None:
                        resources['memory_mb'] = entry['memory_mb']
                    info = await asyncio.wait_for(
                        AsyncTemplate.build(template=template, name=entry['alias'], **resources),
                        timeout=entry['build_timeout_seconds'])
                    # build() returns only after the SDK observed READY. Store
                    # identity digests, not raw provider responses or build logs.
                    row.update(status='built_ready', readiness_verified=True,
                               build_id_sha256=hashlib.sha256(info.build_id.encode()).hexdigest())
                row['finished_at'] = time.time()
                save(out / 'result.json', result)
            result['complete'] = True
        except Exception as exc:
            result['error_type'] = type(exc).__name__
            if result['entries']:
                result['entries'][-1]['error_type'] = type(exc).__name__
            raise
        finally:
            result['finished_at'] = time.time()
            save(out / 'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', default='work/factory-study-02')
    parser.add_argument('--researcher', default='astra')
    parser.add_argument('--scope', choices=['selection', 'final', 'all'], default='final')
    parser.add_argument('--execute', action='store_true', help='perform E2B template preparation')
    parser.add_argument('--out', help='new evidence directory; required with --execute')
    args = parser.parse_args()
    if args.execute and not args.out:
        parser.error('--execute requires a new --out directory')
    try:
        plan = make_plan(args.study, args.researcher, args.scope)
        if not args.execute:
            print(json.dumps(dict(plan, mode='offline_plan'), indent=2))
            return
        result = asyncio.run(execute(plan, args.out))
        print(json.dumps({'complete': result['complete'], 'templates': len(result['entries']),
                          'built': sum(row['status'] == 'built_ready' for row in result['entries']),
                          'model_calls': 0, 'sandbox_creations': 0}))
    except Exception as exc:
        # Network exception text can contain request metadata. Keep it private.
        print(json.dumps({'complete': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
