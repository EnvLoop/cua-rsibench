"""Prepare/launch/collect a three-task selection recovery on a trusted E2B host.

This is remote-control-plane-v1, not the original Mac execution. ``prepare``
is offline. ``launch`` is a separately invoked cloud operation. Repeating
launch with the SAME output directory cannot create or evaluate a second job.
"""
import argparse
import ast
import fcntl
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import shlex
import sys
import tarfile
import time
import uuid

from remote_cloud_worker import VERSION, MAX_BYTES, assert_no_credentials, read_archive, safe_name, sha, write_json

ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = '/work/cua-remote/job'
REMOTE_CONTROL = '/work/cua-remote/control'
REMOTE_PYTHON = '/opt/cua/bin/python'
LEASE = 3600
SOURCE_ROOTS = ('__init__', 'cloud_launch', 'sample_cache', 'tinker_proxy',
                'factory_harbor', 'journal_env', 'command_journal')
PACKAGE_SOURCES = {
    'harbor': ('harbor/environments/e2b.py', 'harbor/trial/trial.py',
               'harbor/trial/single_step.py', 'harbor/trial/artifact_handler.py'),
    'e2b': ('e2b/connection_config.py', 'e2b/envd/client_async/__init__.py',
            'e2b/api/client_async/__init__.py', 'e2b/sandbox_async/commands/command.py'),
    'connectrpc': ('connectrpc/_client_async.py',),
}


def source_closure(root=ROOT):
    """Include exact local imports needed by the package initializer and adapter."""
    pending, found = list(SOURCE_ROOTS), set()
    while pending:
        name = pending.pop()
        if name in found:
            continue
        path = root / 'src/cursibench' / (name + '.py')
        if not path.is_file() or path.is_symlink():
            raise ValueError('required source is missing or linked: ' + name)
        found.add(name)
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.level == 1:
                if node.module:
                    pending.append(node.module)
                else:
                    pending.extend(alias.name for alias in node.names)
    return [root / 'src/cursibench' / (name + '.py') for name in sorted(found)]


def runtime_origin():
    """Resolve Linux dependency closure at the versions installed in Harbor's venv."""
    from packaging.markers import default_environment
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    if sys.version_info[:2] != (3, 12):
        raise ValueError('prepare with work/harbor-venv/bin/python (Python 3.12)')
    environment = default_environment()
    environment.update(sys_platform='linux', platform_system='Linux', os_name='posix',
                       platform_machine='x86_64', python_version='3.12')
    pending = [Requirement(x) for x in ('harbor[e2b]==0.23.0', 'e2b==2.51.0', 'httpx[http2]==0.28.1')]
    versions, extras_seen = {}, {}
    while pending:
        requirement = pending.pop()
        name = canonicalize_name(requirement.name)
        version = importlib.metadata.version(name)
        if requirement.specifier and not requirement.specifier.contains(version, prereleases=True):
            raise ValueError('installed dependency violates its declared requirement: ' + name)
        extras = set(requirement.extras) | extras_seen.get(name, set())
        if name in versions and extras == extras_seen[name]:
            continue
        versions[name], extras_seen[name] = version, extras
        for raw in importlib.metadata.requires(name) or []:
            child = Requirement(raw)
            if child.marker is None or any(child.marker.evaluate(dict(environment, extra=e)) for e in extras | {''}):
                pending.append(child)
    sources = {}
    for distribution, paths in PACKAGE_SOURCES.items():
        package = importlib.metadata.distribution(distribution)
        for relative in paths:
            sources[relative] = {'distribution': distribution, 'path': relative,
                                 'sha256': sha(Path(package.locate_file(relative)).read_bytes())}
    return {'python_origin': sys.version, 'platform_origin': platform.platform(),
            'python_required': '3.12', 'platform_destination': 'Linux x86_64',
            'packages': dict(sorted(versions.items())), 'package_sources': sources}


def reserved_candidate_binding(study, state, researcher, training, selected, attempt_id):
    """Bind only an unevaluated, already-trained pending reservation.

    This returns preparation metadata, never a campaign registration. Missing
    evaluation evidence is accepted only through this explicit narrow path.
    """
    from cursibench.factory_campaign import digest
    study, training = Path(study).resolve(), Path(training).resolve()
    try:
        number = int(attempt_id.split('-')[-1])
    except (ValueError, AttributeError):
        raise ValueError('invalid reserved attempt identity') from None
    if (attempt_id != 'round-' + str(number) or number != len(state['attempts']) + 1
            or not 1 <= number <= state['protocol']['max_attempts']
            or state.get('final_selection') is not None or state.get('baseline') is None):
        raise ValueError('reserved candidate is not the next open campaign attempt')
    reservation = state.get('reservations', {}).get(attempt_id)
    if reservation is None or any(row['attempt_id'] == attempt_id for row in state['attempts']):
        raise ValueError('unevaluated training reservation required')
    expected_training = study / f'round-{number}' / ('train-' + researcher) / 'training.json'
    if training != expected_training.resolve():
        raise ValueError('training manifest path differs from reserved attempt')
    if (study / f'round-{number}' / ('eval-' + researcher)).exists() or (study / f'round-{number}' / (researcher + '-evaluation-process.json')).exists():
        raise ValueError('existing evaluation evidence requires the governed recovery path')
    preflight_path = study / f'round-{number}' / (researcher + '-preflight.json')
    preflight = json.loads(preflight_path.read_text())
    pending_path = study / f'round-{number}' / (researcher + '-evaluation-pending.json')
    if not pending_path.is_file():
        raise ValueError('explicit pending-evaluation receipt required')
    pending = json.loads(pending_path.read_text())
    factory = study / state['protocol'].get('factory_directory', 'factories') / f'factory-{researcher}-{number:02}'
    data_path = factory / 'train_messages.jsonl'
    data_bytes = data_path.read_bytes()
    rows = [json.loads(line) for line in data_bytes.decode().splitlines() if line.strip()]
    factory_result = json.loads((factory / 'result.json').read_text())
    if (not selected.get('verified_training_and_sampling') or preflight.get('accepted') is not True
            or selected.get('data_sha256') != reservation['dataset_hash']
            or preflight.get('data_sha256') != reservation['dataset_hash']
            or selected.get('scheduled_tokens') != preflight.get('scheduled_tokens')
            or not 0 < selected['scheduled_tokens'] == reservation['token_bound']
            or sha(data_bytes) != reservation['dataset_hash']
            or preflight.get('records') != len(rows) or selected.get('record_count') != len(rows)
            or factory_result.get('complete') is not True
            or factory_result.get('submission', {}).get('validated') is not True
            or factory_result['submission'].get('records') != len(rows)):
        raise ValueError('reserved training/preflight provenance mismatch')
    if (pending.get('status') != 'awaiting_evaluation' or pending.get('researcher') != researcher
            or pending.get('attempt') != attempt_id or pending.get('evaluation_started') is not False
            or pending.get('training_reservation_retained') is not True
            or pending.get('training_manifest') != str(training.relative_to(study))
            or pending.get('training_manifest_sha256') != sha(training.read_bytes())
            or pending.get('data_sha256') != reservation['dataset_hash']
            or pending.get('scheduled_tokens') != reservation['token_bound']
            or pending.get('selection_manifest_sha256') != state['protocol']['selection_manifest_sha256']
            or not isinstance(pending.get('created_at'), (int, float))
            or pending['created_at'] < reservation['reserved_at']):
        raise ValueError('pending-evaluation receipt differs from reserved candidate')
    if (selected.get('training_profile') != 'factory-v1' or selected.get('steps_requested') != 32
            or [event.get('step') for event in selected.get('events', [])] != list(range(1, 33))
            or selected.get('batch_size') != 2 or selected.get('covered_records') != len(rows)):
        raise ValueError('reserved candidate requires all 32 verified updates and full data coverage')
    record = {'attempt_id': attempt_id, 'dataset_hash': reservation['dataset_hash'],
              'training_tokens': selected['scheduled_tokens']}
    provenance = {'reservation_sha256': digest(reservation),
                  'preflight_sha256': sha(preflight_path.read_bytes()),
                  'pending_evaluation_receipt_sha256': sha(pending_path.read_bytes()),
                  'submitted_dataset_sha256': sha(data_bytes),
                  'factory_result_sha256': sha((factory / 'result.json').read_bytes()),
                  'training_manifest_sha256': sha(training.read_bytes()),
                  'local_evaluation_absent_at_preparation': True,
                  'registration_required_after_independent_audit': True}
    return record, provenance


def prepare(study, researcher, training, base, out, reserved_attempt=None):
    from cursibench.factory_campaign import CampaignRegistry, digest
    from cursibench.factory_final import validate_study
    from cursibench.factory_provenance import validate_selection_packages
    from cursibench.cloud_launch import model_input
    study, out = Path(study).resolve(), Path(out).resolve()
    if not researcher.isalnum():
        raise ValueError('invalid campaign alias')
    if bool(training) == bool(base):
        raise ValueError('choose exactly one verified training manifest or base')
    if reserved_attempt and base:
        raise ValueError('a reserved candidate requires its verified training manifest')
    state = CampaignRegistry(study / (researcher + '-campaign.json')).snapshot()
    validate_study(ROOT, study, state)
    integrity = validate_selection_packages(ROOT, study, state)
    names = sorted(integrity['task_package_hashes'])
    if len(names) != 3:
        raise ValueError('remote pilot is limited to the full three-task selection suite')
    selected = model_input(training, base=base)
    if selected['model'] != 'Qwen/Qwen3.5-4B':
        raise ValueError('remote pilot requires the frozen student model')
    reservation_provenance = None
    if training:
        training = Path(training).resolve()
        if reserved_attempt:
            record, reservation_provenance = reserved_candidate_binding(study, state, researcher, training, selected, reserved_attempt)
        else:
            records = [r for r in state['attempts'] if r.get('training_manifest') and Path(r['training_manifest']).resolve() == training]
            if len(records) != 1 or selected['data_sha256'] != records[0]['dataset_hash']:
                raise ValueError('checkpoint is not bound to the campaign candidate')
            record = records[0]
        if (selected.get('training_profile') != 'factory-v1' or selected.get('steps_requested') != 32
                or len(selected.get('events', [])) != 32 or selected.get('batch_size') != 2
                or selected.get('covered_records') != selected.get('record_count')
                or selected.get('scheduled_tokens') != record['training_tokens']):
            raise ValueError('training evidence differs from the fixed protocol')
        prior_execution_sha = None
        if not reserved_attempt:
            number = int(record['attempt_id'].split('-')[-1])
            original = (Path(record['evaluation_path']) if record.get('evaluation_path') else
                        study / ('cache-repair/' + researcher if number == 1 and not state['protocol'].get('round1_layout')
                                 else f'round-{number}/eval-{researcher}'))
            original_wrapper = original / 'result.json'
            wrapper = json.loads(original_wrapper.read_text())
            if wrapper.get('training_checkpoint') != selected['checkpoint'] or wrapper.get('training_model') != selected['model']:
                raise ValueError('checkpoint differs from the candidate actually evaluated')
            prior_execution_sha = sha(original_wrapper.read_bytes())
    else:
        prior_execution_sha = None
    runtime = runtime_origin()
    mapping = {}
    for path in source_closure():
        mapping[str(path.relative_to(ROOT))] = path
    mapping['tools/run_cloud_chain.py'] = ROOT / 'tools/run_cloud_chain.py'
    for name in names:
        package = study / 'selection' / name
        for path in sorted(package.rglob('*')):
            if path.is_symlink():
                raise ValueError('task packages must contain regular files only')
            if path.is_file():
                mapping['tasks/' + name + '/' + str(path.relative_to(package))] = path
    if training:
        mapping['inputs/training.json'] = training
    blobs, files = {}, {}
    for name, path in mapping.items():
        safe_name(name)
        data = path.read_bytes()
        assert_no_credentials(data, [os.environ.get('E2B_API_KEY'), os.environ.get('TINKER_API_KEY'), os.environ.get('OPENAI_API_KEY')])
        key = sha(data)
        blobs[key] = data  # identical Kanboard archives and files are uploaded once
        files[name] = {'sha256': key, 'bytes': len(data), 'mode': path.stat().st_mode & 0o777,
                       'origin': str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else 'selected-training-manifest'}
    worker = (ROOT / 'tools/remote_cloud_worker.py').read_bytes()
    manifest = {'operational_version': VERSION, 'job_id': uuid.uuid4().hex,
                'campaign': researcher, 'attempt_id': record['attempt_id'] if training else 'base',
                'purpose': ('first evaluation of an already-trained reserved candidate on the versioned remote controller'
                            if reserved_attempt else 'governed operational recovery of a frozen selection checkpoint; not a new candidate'),
                'execution_kind': 'reserved-candidate-first-evaluation' if reserved_attempt else 'registered-candidate-recovery',
                'admission_kind': 'reserved_initial_evaluation' if reserved_attempt else 'registered_candidate_recovery',
                'reservation_provenance': reservation_provenance,
                'protocol_hash': state['protocol_hash'], 'selection_integrity': integrity,
                'task_names': names, 'files': files, 'runtime': runtime,
                'model': {'name': selected['model'], 'kind': selected['inference_kind'],
                          'checkpoint_sha256': digest(selected['checkpoint']),
                          'prior_execution_wrapper_sha256': prior_execution_sha},
                'worker_sha256': sha(worker),
                'fixed': {'agent_actions': 90, 'agent_timeout_seconds': 1500,
                          'temperature': 0, 'seed': 23, 'output_tokens': 512,
                          'environment': 'journal', 'concurrency': 3, 'child_job_cap_seconds': 2700},
                'orchestrator_lease_seconds': LEASE,
                'credentials': {'orchestrator': ['E2B_API_KEY', 'TINKER_API_KEY'],
                                'proxy': ['TINKER_API_KEY', 'ephemeral proxy bearer'],
                                'actor': [], 'verifier': [], 'research_workspace': []}}
    manifest_bytes = json.dumps(manifest, sort_keys=True).encode()
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for name, data in [('manifest.json', manifest_bytes), *[('blobs/' + key, data) for key, data in sorted(blobs.items())]]:
            entry = tarfile.TarInfo(name)
            entry.mode, entry.size = 0o600, len(data)
            archive.addfile(entry, io.BytesIO(data))
    data = payload.getvalue()
    if len(data) > MAX_BYTES or sum(len(blob) for blob in blobs.values()) > MAX_BYTES:
        raise ValueError('payload exceeds bounded size')
    out.mkdir(parents=True, exist_ok=False)
    out.chmod(0o700)
    (out / 'payload.tar.gz').write_bytes(data)
    (out / 'worker.py').write_bytes(worker)
    write_json(out / 'manifest.json', manifest)
    plan = {'operational_version': VERSION, 'job_id': manifest['job_id'],
            'admission_kind': manifest['admission_kind'],
            'prepared_at': time.time(), 'payload_sha256': sha(data), 'manifest_sha256': sha(manifest_bytes),
            'worker_sha256': sha(worker), 'payload_bytes': len(data), 'unique_blobs': len(blobs),
            'materialized_files': len(files), 'task_names': names,
            'credential_values_present': False, 'orchestrator_lease_seconds': LEASE,
            'runtime_platform_change': 'Mac control plane to separate trusted Linux E2B control plane'}
    write_json(out / 'plan.json', plan)
    return plan


def checked_inputs(out):
    plan = json.loads((out / 'plan.json').read_text())
    if sha((out / 'payload.tar.gz').read_bytes()) != plan['payload_sha256'] or sha((out / 'worker.py').read_bytes()) != plan['worker_sha256']:
        raise ValueError('prepared inputs changed')
    return plan


def bounded_upload(sandbox, remote, data):
    """Three idempotent exact-byte uploads/readbacks; no command/model replay."""
    for attempt in range(3):
        try:
            sandbox.files.write(remote, data, user='root', request_timeout=60)
            actual = sandbox.files.read(remote, format='bytes', user='root', request_timeout=60)
            if sha(actual) != sha(data):
                raise ValueError('remote upload hash mismatch')
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def connect_existing(state):
    from e2b import Sandbox
    if time.time() >= state['lease_deadline_upper_bound']:
        raise ValueError('orchestrator lease expired; never recreate this job automatically')
    return Sandbox.connect(state['sandbox_id'])  # no timeout renewal


def launch(out, template):
    from e2b import Sandbox
    out = Path(out).resolve()
    plan = checked_inputs(out)
    state_path = out / 'lifecycle.json'
    with (out / 'local.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if state.get('collected') or state.get('orchestrator_destroyed'):
            return {'state': 'already_collected_or_destroyed'}
        if not state:
            for name in ('E2B_API_KEY', 'TINKER_API_KEY'):
                if not os.environ.get(name):
                    raise ValueError('required provider credential missing')
            state = {'job_id': plan['job_id'], 'template': template, 'create_intent_at': time.time()}
            write_json(state_path, state)  # ambiguous create is never blindly repeated
            sandbox = Sandbox.create(template=template, timeout=LEASE,
                                     metadata={'project': 'cua-rsibench', 'role': 'trusted-orchestrator', 'remote_job_id': plan['job_id']},
                                     envs={name: os.environ[name] for name in ('E2B_API_KEY', 'TINKER_API_KEY')})
            state.update(sandbox_id=sandbox.sandbox_id,
                         lease_deadline_upper_bound=state['create_intent_at'] + LEASE,
                         sandbox_created_at=time.time())
            write_json(state_path, state)
        elif not state.get('sandbox_id'):
            raise ValueError('previous create has no receipt; inspect provider metadata before manual adoption')
        else:
            if template != state['template']:
                raise ValueError('orchestrator template changed')
            sandbox = connect_existing(state)
        if not state.get('dispatch_requested_at'):
            # /tmp exists in every template; worker/control dirs are made by the worker.
            bounded_upload(sandbox, '/tmp/cua-remote-payload.tar.gz', (out / 'payload.tar.gz').read_bytes())
            bounded_upload(sandbox, '/tmp/cua-remote-worker.py', (out / 'worker.py').read_bytes())
            state['uploads_verified_at'] = time.time()
            state['dispatch_requested_at'] = time.time()
            write_json(state_path, state)
        command = ['nohup', REMOTE_PYTHON, '/tmp/cua-remote-worker.py', '--root', REMOTE_ROOT,
                   '--payload', '/tmp/cua-remote-payload.tar.gz', '--payload-sha', plan['payload_sha256'],
                   '--manifest-sha', plan['manifest_sha256'], '--worker-sha', plan['worker_sha256'],
                   '--lease-deadline', str(state['lease_deadline_upper_bound'])]
        shell = ' '.join(shlex.quote(word) for word in command) + ' >/tmp/cua-remote-dispatch.log 2>&1 </dev/null &'
        # Explicit launch retry uses the same sandbox/payload and durable worker
        # sentinel. It can start a supervisor process, never a second evaluation.
        try:
            sandbox.commands.run(shell, user='root', timeout=15)
            state['dispatch_ack_at'] = time.time()
        except Exception as exc:
            state['dispatch_ack_error_type'] = type(exc).__name__
        write_json(state_path, state)
        return {'state': 'dispatch_requested', 'acknowledged': 'dispatch_ack_at' in state,
                'job_id': plan['job_id'], 'lease_seconds': LEASE}


def verified_evidence(data, completion):
    if len(data) != completion['archive_bytes'] or sha(data) != completion['archive_sha256']:
        raise ValueError('downloaded archive hash mismatch')
    files = read_archive(data)
    index_bytes = files.get('evidence-index.json', b'')
    if sha(index_bytes) != completion['evidence_index_sha256']:
        raise ValueError('evidence index hash mismatch')
    index = json.loads(index_bytes)
    if set(files) != {'evidence/' + name for name in index['files']} | {'evidence-index.json'}:
        raise ValueError('evidence file set mismatch')
    for name, row in index['files'].items():
        safe_name(name)
        content = files['evidence/' + name]
        if sha(content) != row['sha256'] or len(content) != row['bytes']:
            raise ValueError('downloaded evidence file mismatch')
    return files, index


def collect(out, download=True):
    out = Path(out).resolve()
    plan = checked_inputs(out)
    state_path = out / 'lifecycle.json'
    with (out / 'local.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(state_path.read_text())
        if state.get('collected') and state.get('orchestrator_destroyed'):
            return {'state': 'collected', 'orchestrator_destroyed': True}
        sandbox = connect_existing(state)
        try:
            completion = json.loads(sandbox.files.read(REMOTE_CONTROL + '/completion.json', user='root', request_timeout=30))
        except Exception as exc:
            # Missing receipt or local transport failure is an observation state,
            # not permission to re-create or re-run a cloud evaluation.
            return {'state': 'completion_unobserved', 'poll_error_type': type(exc).__name__}
        if (completion['payload_sha256'] != plan['payload_sha256']
                or completion['manifest_sha256'] != plan['manifest_sha256']):
            raise ValueError('remote completion belongs to another payload')
        write_json(out / 'remote-completion.json', completion)
        if not completion.get('complete'):
            return {'state': 'remote_error', 'error_type': completion.get('error_type'),
                    'evaluation_dispatched': completion.get('evaluation_dispatched')}
        if not download:
            return {'state': 'evidence_ready', 'archive_sha256': completion['archive_sha256']}
        if not state.get('collected'):
            for attempt in range(3):
                try:
                    data = sandbox.files.read(REMOTE_CONTROL + '/evidence.tar.gz', format='bytes', user='root', request_timeout=60)
                    files, index = verified_evidence(data, completion)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
            (out / 'evidence.tar.gz').write_bytes(data)
            destination = out / 'evaluation'
            staging = destination if destination.exists() else out / 'evaluation.partial'
            staging.mkdir(exist_ok=True)
            for name in index['files']:
                path = staging / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    if path.is_symlink() or sha(path.read_bytes()) != index['files'][name]['sha256']:
                        raise ValueError('existing partial evidence differs from verified archive')
                else:
                    path.write_bytes(files['evidence/' + name])
            actual = {str(p.relative_to(staging)) for p in staging.rglob('*') if p.is_file()}
            if actual != set(index['files']):
                raise ValueError('extra files in evidence destination')
            if staging != destination:
                staging.rename(destination)
            write_json(out / 'evidence-index.json', index)
            state.update(collected=True, collected_at=time.time(), archive_sha256=completion['archive_sha256'])
            write_json(state_path, state)
        try:
            sandbox.kill()
            state['orchestrator_destroyed'] = True
        except Exception as exc:
            state['cleanup_error_type'] = type(exc).__name__
        write_json(state_path, state)
        return {'state': 'collected', 'orchestrator_destroyed': state.get('orchestrator_destroyed', False),
                'evaluation_path': str(out / 'evaluation')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--study', required=True)
    p.add_argument('--researcher', required=True)
    p.add_argument('--training')
    p.add_argument('--base', action='store_true')
    p.add_argument('--reserved-attempt', help='explicit unevaluated pending reservation, e.g. round-2')
    p.add_argument('--out', required=True)
    for name in ('launch', 'status', 'collect'):
        p = sub.add_parser(name)
        p.add_argument('--out', required=True)
        if name == 'launch':
            p.add_argument('--template', required=True)
    args = parser.parse_args()
    try:
        if args.mode == 'prepare':
            result = prepare(args.study, args.researcher, args.training, args.base, args.out, args.reserved_attempt)
        elif args.mode == 'launch':
            result = launch(args.out, args.template)
        else:
            result = collect(args.out, download=args.mode == 'collect')
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({'state': 'error', 'error_type': type(exc).__name__}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
