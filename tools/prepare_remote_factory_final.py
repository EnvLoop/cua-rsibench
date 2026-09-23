"""Offline preparation and reviewed admission of INITIAL frozen remote finals.

Launch/collect each prepared chunk with run_cloud_chain_remote.py. This tool
never launches cloud work and never treats an initial final as a recovery.
"""
import argparse
import fcntl
import io
import json
import os
from pathlib import Path
import re
import tarfile
import tempfile
import time
import uuid

from cursibench.cloud_launch import model_input
from cursibench.factory_campaign import CampaignRegistry, digest
from cursibench.factory_final import make_plan, combine, verify_execution
from cursibench.factory_results import summarize
from cursibench.factory_roster import study_roster
from prepare_remote_final_recovery import FIXED, LEASE, ready_controller
from remote_cloud_worker import VERSION, MAX_BYTES, assert_no_credentials, safe_name, sha, write_json, unpack_payload, verify_materialized, read_archive
from remote_evidence_audit import audit_remote
from run_cloud_chain_remote import source_closure, runtime_origin, checked_inputs

ROOT = Path(__file__).resolve().parents[1]
PREPARATION_VERSION = 'remote-initial-final-v1'


def read(path):
    return json.loads(Path(path).read_text())


def file_sha(path):
    return sha(Path(path).read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def frozen_context(study):
    """Require the declared stopping condition for every campaign, then its seal."""
    study = Path(study).resolve()
    states = {name: CampaignRegistry(study / (name + '-campaign.json')).snapshot()
              for name in study_roster(study)}
    for name, state in states.items():
        protocol = state['protocol']
        require(not state['reservations'], 'pending training prevents final preparation: ' + name)
        require(state['baseline'] is not None and state['final_selection'] is not None,
                'all campaign selections must be frozen: ' + name)
        require(len(state['attempts']) <= protocol['max_attempts'] and
                0 <= state['used_training_tokens'] <= protocol['training_token_budget'], 'campaign exceeds its declared budget')
        stopped = (len(state['attempts']) == protocol['max_attempts'] or state['best_score'] == 1 or
                   state['used_training_tokens'] + 262144 > protocol['training_token_budget'])
        require(stopped, 'declared search stopping condition not reached: ' + name)
        frozen = state['final_selection']
        require(frozen['candidate'] == state['selected'] and frozen['selection_score'] == state['best_score']
                and frozen['protocol_hash'] == state['protocol_hash'], 'frozen selection differs from campaign')
    comparison = read(study / 'final-comparison.json')
    frozen_times = {name: state['final_selection']['frozen_at'] for name, state in states.items()}
    require(comparison.get('selection_frozen_at') == frozen_times and
            comparison['created_at'] >= max(frozen_times.values()), 'comparison does not follow all frozen selections')
    reference = next(iter(states))
    identities = {'base': make_plan(ROOT, study, states[reference], 'base')['binding']['checkpoint_sha256']}
    identities.update({name: make_plan(ROOT, study, state, 'selected')['binding']['checkpoint_sha256']
                       for name, state in states.items()})
    executions, bindings, unique = [], {}, {}
    for role, checkpoint in identities.items():
        if checkpoint not in unique:
            name = reference if role == 'base' else role
            purpose = 'base' if role == 'base' else 'selected'
            labels = []
            for repetition in (1, 2):
                label = f'{name}-{purpose}-repeat-{repetition}'
                labels.append(label)
                executions.append({'label': label, 'researcher': name, 'role': purpose,
                                   'repetition': repetition, 'checkpoint_sha256': checkpoint})
            unique[checkpoint] = labels
        bindings[role] = unique[checkpoint]
    require(comparison.get('repetitions') == 2 and comparison.get('executions') == executions
            and comparison.get('bindings') == bindings, 'frozen comparison slots or checkpoint sharing differ')
    return states, comparison


def slot_plan(study, label, states, comparison):
    require(bool(re.fullmatch(r'[a-z0-9-]+', label)), 'invalid final comparison label')
    matches = [row for row in comparison['executions'] if row['label'] == label]
    require(len(matches) == 1, 'label is not one frozen comparison execution slot')
    execution = matches[0]
    plan = make_plan(ROOT, study, states[execution['researcher']], execution['role'], execution['repetition'])
    require(plan['binding']['checkpoint_sha256'] == execution['checkpoint_sha256'], 'slot checkpoint differs')
    require(len(plan['chunks']) == 2 and all(len(names) == 3 for names in plan['chunks'].values()),
            'initial final requires two complete three-task chunks')
    names = [name for chunk in plan['chunks'].values() for name in chunk]
    require(len(names) == len(set(names)) == 6 and set(names) == set(plan['task_package_hashes']), 'final task identities differ')
    require(plan['sampling'] == {'max_tokens': 512, 'temperature': 0, 'seed': 23}, 'final sampling differs')
    return execution, plan


def initial_binding(label, chunk, comparison_sha, plan_sha, final_plan):
    return {'logical_comparison_slot': label, 'chunk': chunk,
            'final_comparison_sha256': comparison_sha, 'final_plan_sha256': plan_sha,
            'task_package_hashes': {name: final_plan['task_package_hashes'][name]
                                   for name in final_plan['chunks'][chunk]}}


def prepare_chunk(study, label, execution, final_plan, chunk, out, runtime, controller, comparison_sha, plan_sha):
    """Same content-addressed wire format, with an explicit initial-final binding."""
    mapping = {path.relative_to(ROOT).as_posix(): path for path in source_closure(ROOT)}
    mapping['tools/run_cloud_chain.py'] = ROOT / 'tools/run_cloud_chain.py'
    names = final_plan['chunks'][chunk]
    for name in names:
        package = study / 'sealed-final' / chunk / name
        for path in sorted(package.rglob('*')):
            require(not path.is_symlink(), 'frozen final package contains a symlink')
            if path.is_file():
                mapping['tasks/' + name + '/' + path.relative_to(package).as_posix()] = path
    binding = final_plan['binding']
    training = binding['training_manifest']
    if training:
        mapping['inputs/training.json'] = Path(training)
    selected = model_input(training, base=binding['candidate'] == 'base', model=binding['model'])
    require(digest(selected['checkpoint']) == binding['checkpoint_sha256'], 'selected checkpoint changed')
    blobs, files = {}, {}
    for name, path in mapping.items():
        safe_name(name)
        data = path.read_bytes()
        assert_no_credentials(data, [os.environ.get(key) for key in ('E2B_API_KEY', 'TINKER_API_KEY', 'OPENAI_API_KEY')])
        key = sha(data)
        blobs[key] = data
        files[name] = {'sha256': key, 'bytes': len(data), 'mode': path.stat().st_mode & 0o777,
                       'origin': path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else 'selected-training-manifest'}
    worker = (ROOT / 'tools/remote_cloud_worker.py').read_bytes()
    initial = initial_binding(label, chunk, comparison_sha, plan_sha, final_plan)
    manifest = {'operational_version': VERSION, 'job_id': uuid.uuid4().hex,
                'campaign': execution['researcher'], 'attempt_id': binding['candidate'],
                'purpose': 'initial final evaluation of a frozen comparison slot',
                'execution_kind': 'frozen-initial-final', 'admission_kind': 'initial_final',
                'protocol_hash': final_plan['protocol_hash'], 'task_names': names, 'files': files, 'runtime': runtime,
                'model': {'name': selected['model'], 'kind': selected['inference_kind'],
                          'checkpoint_sha256': binding['checkpoint_sha256']},
                'worker_sha256': sha(worker), 'fixed': FIXED, 'orchestrator_lease_seconds': LEASE,
                'initial_final': initial, 'controller_template': controller,
                'credentials': {'orchestrator': ['E2B_API_KEY', 'TINKER_API_KEY'],
                                'proxy': ['TINKER_API_KEY', 'ephemeral proxy bearer'],
                                'actor': [], 'verifier': [], 'research_workspace': []}}
    encoded = json.dumps(manifest, sort_keys=True).encode()
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name, data in [('manifest.json', encoded), *[('blobs/' + key, value) for key, value in sorted(blobs.items())]]:
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = 0o600, len(data)
            archive.addfile(entry, io.BytesIO(data))
    payload = stream.getvalue()
    require(len(payload) <= MAX_BYTES and sum(map(len, blobs.values())) <= MAX_BYTES, 'remote payload exceeds byte bound')
    with tempfile.TemporaryDirectory(prefix='cua-initial-final-verify-') as temporary:
        materialized = Path(temporary)
        restored = unpack_payload(payload, materialized, sha(encoded))
        verify_materialized(materialized, restored)
        require(restored == manifest, 'payload manifest differs after round-trip')
    plan = {'operational_version': VERSION, 'job_id': manifest['job_id'], 'admission_kind': 'initial_final',
            'prepared_at': time.time(), 'payload_sha256': sha(payload), 'manifest_sha256': sha(encoded),
            'worker_sha256': sha(worker), 'payload_bytes': len(payload), 'unique_blobs': len(blobs),
            'materialized_files': len(files), 'task_names': names, 'credential_values_present': False,
            'orchestrator_lease_seconds': LEASE, 'controller_template': controller['template'],
            'runtime_platform_change': 'initial final uses the versioned trusted Linux E2B controller',
            'initial_final': initial, 'cloud_execution_authorized_by_this_preparation': False}
    # Publish only a complete child directory. A preparation interrupted between
    # chunks can resume without replacing an existing job identity or evidence.
    with tempfile.TemporaryDirectory(prefix='.' + chunk + '-', dir=out.parent) as temporary:
        stage = Path(temporary) / 'payload'
        stage.mkdir(mode=0o700)
        (stage / 'payload.tar.gz').write_bytes(payload)
        (stage / 'payload.tar.gz').chmod(0o600)
        (stage / 'worker.py').write_bytes(worker)
        write_json(stage / 'manifest.json', manifest)
        write_json(stage / 'plan.json', plan)
        stage.rename(out)
    return plan


def validate_chunk(directory, label, chunk, final_plan, comparison_sha, plan_sha):
    child = checked_inputs(directory)
    payload = read_archive((directory / 'payload.tar.gz').read_bytes())
    require(sha(payload['manifest.json']) == child['manifest_sha256'], 'child manifest hash changed')
    manifest = json.loads(payload['manifest.json'])
    require(manifest == read(directory / 'manifest.json'), 'saved child manifest differs from payload')
    expected = initial_binding(label, chunk, comparison_sha, plan_sha, final_plan)
    require(child.get('admission_kind') == manifest.get('admission_kind') == 'initial_final', 'not an initial final')
    require(child.get('operational_version') == manifest.get('operational_version') == VERSION and
            manifest.get('execution_kind') == 'frozen-initial-final', 'initial-final operational version differs')
    require(child.get('initial_final') == manifest.get('initial_final') == expected, 'initial final scope changed')
    require('final_recovery' not in manifest and 'prior_execution_wrapper_sha256' not in manifest['model'],
            'initial final must not fabricate recovery history')
    require(manifest['fixed'] == FIXED and manifest['protocol_hash'] == final_plan['protocol_hash'], 'fixed runtime settings differ')
    require(child['task_names'] == manifest['task_names'] == final_plan['chunks'][chunk], 'chunk task identities differ')
    require(manifest['model']['checkpoint_sha256'] == final_plan['binding']['checkpoint_sha256'], 'child checkpoint differs')
    require(manifest['model']['name'] == final_plan['binding']['model'] and manifest['model']['kind'] ==
            ('base' if final_plan['binding']['candidate'] == 'base' else 'checkpoint'), 'child model kind differs')
    require(manifest['worker_sha256'] == child['worker_sha256'], 'child worker identity differs')
    require(manifest['job_id'] == child['job_id'], 'child job identity differs')
    expected_blobs = {'manifest.json'} | {'blobs/' + row['sha256'] for row in manifest['files'].values()}
    require(set(payload) == expected_blobs, 'child input blob set differs')
    for row in manifest['files'].values():
        blob = payload['blobs/' + row['sha256']]
        require(sha(blob) == row['sha256'] and len(blob) == row['bytes'], 'child input blob differs')
    for name in final_plan['chunks'][chunk]:
        prefix = 'tasks/' + name + '/'
        hashes = {key[len(prefix):]: row['sha256'] for key, row in manifest['files'].items() if key.startswith(prefix)}
        require(digest(hashes) == final_plan['task_package_hashes'][name], 'sealed child task package differs')
    for name, expected_hash in final_plan['runtime_hashes'].items():
        if name in manifest['files']:
            require(manifest['files'][name]['sha256'] == expected_hash, 'frozen child runtime differs')
    trusted = read(ROOT / 'docs/evidence/remote-controller-sources-v1.json')
    require(manifest['worker_sha256'] == trusted['worker_sha256'] and
            manifest['operational_version'] == trusted['operational_version'],
            'child worker or version differs from trusted source snapshot')
    supplied_sources = {key: row['sha256'] for key, row in manifest['files'].items()
                        if key.startswith(('src/', 'tools/'))}
    require(supplied_sources == trusted['files'], 'child trusted source inventory or bytes differ')
    allowed_inputs = set(trusted['files']) | {
        key for key in manifest['files']
        if key.startswith(tuple('tasks/' + name + '/' for name in child['task_names']))}
    if manifest['model']['kind'] == 'checkpoint':
        allowed_inputs.add('inputs/training.json')
    require(set(manifest['files']) == allowed_inputs, 'child payload includes unexpected input paths')
    return child


def validate_operation(directory, label, final_plan, comparison, states):
    require(read(directory / 'plan.json') == final_plan, 'immutable final plan differs from make_plan')
    operation = read(directory / 'operational-plan.json')
    comparison_sha = file_sha(directory.parent.parent / 'final-comparison.json')
    plan_sha = file_sha(directory / 'plan.json')
    require(operation['admission_kind'] == 'initial_final' and operation['preparation_version'] == PREPARATION_VERSION,
            'wrong initial-final operational version')
    execution = next(row for row in comparison['executions'] if row['label'] == label)
    require(operation['operational_version'] == VERSION and operation['fixed'] == FIXED and
            all(operation[key] == execution[key] for key in ('researcher', 'role', 'repetition')),
            'operational slot settings differ')
    require(operation['logical_comparison_slot'] == label and operation['final_comparison_sha256'] == comparison_sha
            and operation['final_plan_sha256'] == plan_sha, 'operational plan binding differs')
    frozen_times = {name: state['final_selection']['frozen_at'] for name, state in states.items()}
    require(operation['selection_frozen_at'] == frozen_times and operation['prepared_at'] >= comparison['created_at'],
            'preparation precedes frozen comparison')
    require(operation['checkpoint_sha256'] == final_plan['binding']['checkpoint_sha256'], 'operational checkpoint differs')
    require(set(operation['child_plan_sha256']) == set(final_plan['chunks']), 'child plan set differs')
    for chunk in final_plan['chunks']:
        require(file_sha(directory / chunk / 'plan.json') == operation['child_plan_sha256'][chunk], 'child plan changed')
        child = validate_chunk(directory / chunk, label, chunk, final_plan, comparison_sha, plan_sha)
        require(child['controller_template'] == operation['controller_template']['template'], 'controller template differs')
    return operation


def prepare(study, template_directory, labels=None):
    study = Path(study).resolve()
    states, comparison = frozen_context(study)
    requested = labels if labels is not None else [row['label'] for row in comparison['executions']]
    require(requested and len(requested) == len(set(requested)), 'unique comparison labels required')
    slots = [(label, *slot_plan(study, label, states, comparison)) for label in requested]
    runtime = runtime_origin()
    controller = ready_controller(Path(template_directory).resolve(), runtime)
    comparison_sha = file_sha(study / 'final-comparison.json')
    parent = study / 'final-executions'
    parent.mkdir(exist_ok=True)
    prepared = []
    with (parent / '.initial-final-preparation.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for label, execution, final_plan in slots:
            directory = parent / label
            if (directory / 'operational-plan.json').exists():
                operation = validate_operation(directory, label, final_plan, comparison, states)
                require(operation['controller_template'] == controller, 'existing controller proof changed')
                prepared.append(label)
                continue
            intent_path = directory / 'preparation-intent.json'
            require(not directory.exists() or intent_path.exists() or not any(directory.iterdir()),
                    'unowned existing final evidence must not be replaced')
            directory.mkdir(exist_ok=True)
            plan_bytes = json.dumps(final_plan, indent=2).encode()
            identity = {'preparation_version': PREPARATION_VERSION, 'admission_kind': 'initial_final',
                        'logical_comparison_slot': label, 'final_comparison_sha256': comparison_sha,
                        'final_plan_sha256': sha(plan_bytes), 'controller_template': controller}
            if intent_path.exists():
                intent = read(intent_path)
                require(all(intent.get(key) == value for key, value in identity.items()), 'preparation resume binding changed')
            else:
                intent = dict(identity, prepared_at=time.time())
                write_json(intent_path, intent)
            if (directory / 'plan.json').exists():
                require((directory / 'plan.json').read_bytes() == plan_bytes, 'existing final plan differs')
            else:
                write_json(directory / 'plan.json', final_plan)
            plans = {}
            for chunk in sorted(final_plan['chunks']):
                out = directory / chunk
                if out.exists():
                    validate_chunk(out, label, chunk, final_plan, comparison_sha, identity['final_plan_sha256'])
                else:
                    prepare_chunk(study, label, execution, final_plan, chunk, out, runtime, controller,
                                  comparison_sha, identity['final_plan_sha256'])
                plans[chunk] = file_sha(out / 'plan.json')
            operation = dict(identity, operational_version=VERSION, prepared_at=intent['prepared_at'],
                             researcher=execution['researcher'], role=execution['role'], repetition=execution['repetition'],
                             checkpoint_sha256=execution['checkpoint_sha256'], fixed=FIXED,
                             selection_frozen_at={name: state['final_selection']['frozen_at'] for name, state in states.items()},
                             child_plan_sha256=plans, cloud_calls=0, initial_final=True,
                             admission_requires_root_review=True, creator_source_sha256=file_sha(__file__))
            write_json(directory / 'operational-plan.json', operation)
            validate_operation(directory, label, final_plan, comparison, states)
            prepared.append(label)
    return {'state': 'prepared_offline', 'admission_kind': 'initial_final', 'labels': prepared,
            'chunks_per_slot': 2, 'tasks_per_slot': 6, 'cloud_calls': 0, 'controller_template': controller['template']}


def finalize(study, label, admit=False):
    """Verify first; record the initial outcome once only with explicit admission."""
    study = Path(study).resolve()
    states, comparison = frozen_context(study)
    execution, final_plan = slot_plan(study, label, states, comparison)
    directory = study / 'final-executions' / label
    with (directory / '.finalization.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        operation = validate_operation(directory, label, final_plan, comparison, states)
        pieces, proofs = [], {}
        for chunk, names in sorted(final_plan['chunks'].items()):
            child = directory / chunk
            proof = audit_remote(child, names, final_plan['binding']['checkpoint_sha256'], final_plan)
            require(proof['admission_kind'] == 'initial_final', 'collected evidence is not an initial final')
            require(proof['started_at'] >= max(operation['prepared_at'], comparison['created_at'],
                                             *operation['selection_frozen_at'].values()), 'final execution precedes frozen preparation')
            summary = summarize(child / 'evaluation', names)
            for path in (child / 'evaluation/harbor/checkpoint-browser').glob('*/result.json'):
                raw = read(path)
                reward = (raw.get('verifier_result') or {}).get('rewards', {}).get('reward')
                if not raw.get('exception_info') and type(reward) in (int, float) and reward in (0, 1):
                    require(raw.get('verifier_environment_mode') == 'separate', 'scored task lacks separate verification')
            if not verify_execution(child / 'evaluation', final_plan):
                summary.update(status='infrastructure_error', score=None)
            pieces.append(summary)
            proofs[chunk] = proof
        expected = states[execution['researcher']]['protocol']['final_tasks']
        summary = combine(pieces, expected)
        started_at = min(proof['started_at'] for proof in proofs.values())
        receipt = {'admission_kind': 'initial_final', 'logical_comparison_slot': label,
                   'operational_plan_sha256': file_sha(directory / 'operational-plan.json'),
                   'final_plan_sha256': file_sha(directory / 'plan.json'),
                   'final_comparison_sha256': operation['final_comparison_sha256'],
                   'checkpoint_sha256': final_plan['binding']['checkpoint_sha256'],
                   'child_plan_sha256': operation['child_plan_sha256'], 'started_at': started_at,
                   'started_at_source': 'earliest verified remote worker receipt',
                   'evaluation': summary, 'chunk_proofs': proofs}
        if not admit:
            return dict(receipt, registered=False)
        # Persist only the complete recomputed outcome. Invalid executions remain
        # explicit/null and are never repaired, overwritten or re-executed here.
        if (directory / 'summary.json').exists():
            require(read(directory / 'summary.json') == summary, 'existing final summary differs')
        else:
            write_json(directory / 'summary.json', summary)
        started = {'started_at': started_at, 'label': label, 'source': receipt['started_at_source']}
        if (directory / 'started.json').exists():
            require(read(directory / 'started.json') == started, 'existing final start receipt differs')
        else:
            write_json(directory / 'started.json', started)
        registry = CampaignRegistry(study / (execution['researcher'] + '-campaign.json'))
        existing = [row for row in registry.snapshot()['final_results'] if row['label'] == label]
        if existing:
            require(len(existing) == 1 and existing[0]['evaluation'] == summary and existing[0]['started_at'] == started_at,
                    'registered final outcome differs from verified evidence')
        else:
            registry.record_final(label, summary, started_at)
        receipt['summary_sha256'] = file_sha(directory / 'summary.json')
        target = directory / 'initial-final-receipt.json'
        if target.exists():
            require(read(target) == receipt, 'initial final admission receipt differs')
        else:
            write_json(target, receipt)
        return dict(receipt, registered=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--study', default='work/factory-model6-extension')
    p.add_argument('--template-directory', default='work/remote-controller-template-01')
    p.add_argument('--label', action='append')
    p = sub.add_parser('finalize')
    p.add_argument('--study', default='work/factory-model6-extension')
    p.add_argument('--label', required=True)
    p.add_argument('--admit', action='store_true', help='record once only after root review')
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            result = prepare(args.study, args.template_directory, args.label)
        else:
            proof = finalize(args.study, args.label, args.admit)
            result = {'label': args.label, 'admission_kind': 'initial_final', 'status': proof['evaluation']['status'],
                      'score': proof['evaluation']['score'], 'registered': proof['registered']}
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'state': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
