"""Bind final executions to frozen selections, exact task packages and runtime."""
import hashlib
import json
import inspect
from pathlib import Path
from .factory_campaign import digest, valid_scores
from .factory_cases import digest as case_digest


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def package_hash(path, case_hash, partition):
    path = Path(path)
    case = read(path / 'environment/scenario.json')
    case['targets'] = read(path / 'tests/targets.json')
    contract = read(path / 'contract.json')
    if (case_digest(case) != case_hash or contract.get('case_sha256') != case_hash
            or contract.get('source_partition') != partition
            or case['provenance']['source_split'] != partition):
        raise ValueError('task package does not match sealed case')
    if (path / 'instruction.md').read_text() != case['instruction']:
        raise ValueError('task instruction differs from sealed case')
    # Bind every executable, grader, configuration and application archive as well.
    hashes = {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*')) if p.is_file()}
    return digest(hashes)


def validate_exported_runtime(path, root):
    """The seal covers case data; also require the canonical exported executables."""
    from .kanboard_harbor_export import START, VERIFY_MAIN, CONFIG, DOCKER
    from .kanboard_cases import verify
    path, root = Path(path), Path(root)
    expected = {
        'task.toml': CONFIG+'\n[[artifacts]]\nsource = "/app/observer-errors.jsonl"\n',
        'environment/Dockerfile': DOCKER.replace('kanboard_rpc.py start.sh','kanboard_rpc.py stable_observer.py start.sh'),
        'environment/start.sh': START,
        'tests/verify.py': inspect.getsource(verify)+VERIFY_MAIN,
        'tests/test.sh': '#!/bin/sh\nset -eu\npython /tests/verify.py\n',
        'tests/Dockerfile': 'FROM python:3.12-slim\nWORKDIR /tests\nCOPY . /tests/\n',
    }
    for source, target in [('kanboard_seed.py','kanboard_seed.py'),
                           ('kanboard_rpc_v3.py','kanboard_rpc.py'),('stable_observer.py','stable_observer.py')]:
        expected['environment/'+target] = (root/'src/cursibench'/source).read_text()
    for relative, content in expected.items():
        if (path/relative).read_text() != content:
            raise ValueError('noncanonical task executable: '+relative)
    if sha(path/'environment/kanboard.tar.gz') != '6548946b406bc8640dfe20a884dd9cdf708d8d6c25eeacdabd374a36d5e98237':
        raise ValueError('application archive changed')


def validate_study(root, study, state):
    root, study = Path(root), Path(study)
    protocol = state['protocol']
    if sha(study / 'manifest.json') != protocol['selection_manifest_sha256']:
        raise ValueError('selection manifest changed')
    manifest = read(study / 'manifest.json')
    final = read(study / 'sealed-final/manifest.json')
    if digest(final) != protocol['final_manifest_sha256']:
        raise ValueError('sealed final manifest changed')
    names = [r['task'] for r in final['cases']]
    if len(set(names)) != len(names) or set(names) != set(protocol['final_tasks']):
        raise ValueError('sealed final task identities changed')
    repairs = read(study / 'cache-repair/plan.json')['source_sha256']
    runtime = {}
    for name, expected in manifest['engine_hashes'].items():
        relative = 'src/cursibench/' + name
        expected = repairs.get(relative, expected)
        actual = sha(root / relative)
        if actual != expected:
            raise ValueError('frozen runtime changed: ' + relative)
        runtime[relative] = actual
    for relative, expected in repairs.items():
        if sha(root / relative) != expected:
            raise ValueError('declared runtime repair changed: ' + relative)
        runtime[relative] = expected
    # These helpers are also pinned in the execution plan, before the first run.
    for name in ('harbor_adapter.py', 'cloud_launch.py', 'cloud_env.py', 'factory_final.py'):
        relative = 'src/cursibench/' + name
        runtime[relative] = sha(root / relative)
    packages, chunks = {}, {}
    for row in final['cases']:
        chunk, task = row['chunk'], row['task']
        if '/' in chunk or '/' in task or chunk in ('.', '..') or task in ('.', '..'):
            raise ValueError('invalid final task path')
        path = study / 'sealed-final' / chunk / task
        validate_exported_runtime(path, root)
        packages[task] = package_hash(path, row['case_sha256'], 'final')
        chunks.setdefault(chunk, []).append(task)
    if any(not 1 <= len(tasks) <= 3 for tasks in chunks.values()):
        raise ValueError('invalid final chunk size')
    for chunk, tasks in chunks.items():
        actual = {p.parent.name for p in (study / 'sealed-final' / chunk).glob('*/task.toml')}
        if actual != set(tasks):
            raise ValueError('unexpected tasks in final chunk')
    return {'runtime_hashes': runtime, 'task_package_hashes': packages, 'chunks': chunks,
            'final_manifest_sha256': digest(final)}


def checkpoint_binding(state, study_manifest, role):
    selection = state['final_selection']
    if selection is None:
        raise ValueError('freeze selection before preparing final evaluation')
    if role not in ('selected', 'base'):
        raise ValueError('invalid final comparison role')
    if role == 'base' or selection['candidate'] == 'base':
        return {'candidate': 'base', 'model': study_manifest['student'],
                'training_manifest': None, 'training_manifest_sha256': None,
                'checkpoint_sha256': digest(study_manifest['student'])}
    attempt = next(r for r in state['attempts'] if r['attempt_id'] == selection['candidate'])
    path = Path(selection['training_manifest'])
    metadata = read(path)
    settings = study_manifest['training']
    if (not metadata.get('verified_training_and_sampling') or not metadata.get('checkpoint')
            or str(path) != attempt['training_manifest']
            or metadata['data_sha256'] != attempt['dataset_hash']
            or metadata['scheduled_tokens'] != attempt['training_tokens']
            or metadata['model'] != study_manifest['student']
            or metadata['training_profile'] != settings['profile']
            or metadata['steps_requested'] != settings['steps']
            or len(metadata['events']) != settings['steps']
            or metadata['batch_size'] != settings['batch_size']
            or metadata['covered_records'] != metadata['record_count']):
        raise ValueError('selected checkpoint evidence does not match campaign')
    return {'candidate': selection['candidate'], 'model': metadata['model'],
            'training_manifest': str(path), 'training_manifest_sha256': sha(path),
            'checkpoint_sha256': digest(metadata['checkpoint'])}


def make_plan(root, study, state, role, repetition=1):
    if state['final_selection'] is None:
        raise ValueError('final selection is not frozen')
    if type(repetition) is not int or repetition not in (1, 2):
        raise ValueError('bounded final protocol allows repetitions 1 and 2')
    integrity = validate_study(root, study, state)
    binding = checkpoint_binding(state, read(Path(study) / 'manifest.json'), role)
    return dict(integrity, binding=binding, selection=state['final_selection'],
                protocol_hash=state['protocol_hash'], role=role, repetition=repetition,
                sampling=read(Path(study) / 'manifest.json')['sampling'],
                repeat_interpretation='same-seed fresh-environment stability; not independent research seeds')


def combine(summaries, expected_tasks):
    rows = [row for summary in summaries for row in summary.get('tasks', [])]
    names = [row['task'] for row in rows]
    identity_ok = len(names) == len(set(names)) and set(names) == set(expected_tasks)
    result = {'status': 'infrastructure_error', 'score': None, 'expected_tasks': list(expected_tasks),
              'task_identity_matches': identity_ok, 'tasks': rows}
    if all(s['status'] == 'scored' for s in summaries) and identity_ok:
        result.update(status='scored', score=sum(r['score'] for r in rows) / len(rows))
        if valid_scores(result, expected_tasks) is None:
            result.update(status='infrastructure_error', score=None)
    return result


def verify_execution(path, plan):
    result = read(Path(path) / 'result.json')
    if (digest(result.get('training_checkpoint')) != plan['binding']['checkpoint_sha256']
            or result.get('training_model') != plan['binding']['model']
            or result.get('inference_kind') != ('base' if plan['binding']['candidate'] == 'base' else 'checkpoint')
            or result.get('environment') != 'journal' or result.get('factory_contract') is not True
            or result.get('concurrency') != 3):
        raise ValueError('final execution does not match checkpoint/runtime binding')
    return result.get('harbor_exit') == 0 and result.get('proxy_destroyed') is True and not result.get('error_type')
