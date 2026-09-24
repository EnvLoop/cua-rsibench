"""v0.6 offline final-evaluation preparation for one qualified cell/slot.

This module checks a manifest and its local evidence, then persists an intent
and a deterministic chunk plan. It has no provider imports, credentials, remote
jobs, task execution, result collection, or score generation. Hashes bind
evidence bytes; they do not independently establish the truth of a claimed
smoke test or an account price.

Manifest schema: ``cua-final-cell-v0.6``. See
``docs/plans/v0.6-final-preparation-contract.md`` for the exact fields.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


MANIFEST_SCHEMA = 'cua-final-cell-v0.6'
EVIDENCE_SCHEMA = 'cua-cell-qualification-v0.6'
FREEZE_SCHEMA = 'cua-checkpoint-freeze-v0.6'
PLAN_SCHEMA = 'cua-final-offline-plan-v0.6'
INTENT_SCHEMA = 'cua-final-preparation-intent-v0.6'
HEX = re.compile(r'[0-9a-f]{64}\Z')
SLUG = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
MAX_EVIDENCE_BYTES = 16 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def exact(value: object, fields: set[str], label: str) -> dict:
    require(isinstance(value, dict) and set(value) == fields, f'{label}: wrong fields')
    return value


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def is_hash(value: object) -> bool:
    return isinstance(value, str) and HEX.fullmatch(value) is not None


def is_slug(value: object) -> bool:
    return isinstance(value, str) and SLUG.fullmatch(value) is not None


def is_task_id(value: object) -> bool:
    # Upstream IDs may contain spaces, Unicode, or slash-separated namespaces.
    # They are only JSON identities here and are never interpolated into paths.
    return (isinstance(value, str) and 1 <= len(value) <= 256 and
            value.strip() == value and all(ord(char) >= 32 and ord(char) != 127 for char in value))


def positive_integer(value: object, label: str, maximum: int = 10**9) -> int:
    require(type(value) is int and 1 <= value <= maximum, f'{label}: positive integer required')
    return value


def amount(value: object, label: str, *, positive: bool = False) -> Decimal:
    require(isinstance(value, str), f'{label}: decimal string required')
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise ValueError(f'{label}: invalid decimal') from None
    require(result.is_finite() and result >= 0 and (not positive or result > 0),
            f'{label}: finite {"positive" if positive else "nonnegative"} amount required')
    require(-result.as_tuple().exponent <= 6, f'{label}: at most six decimal places')
    return result


def evidence_file(manifest_dir: Path, reference: object, label: str) -> tuple[Path, bytes]:
    reference = exact(reference, {'path', 'sha256'}, label)
    relative = reference['path']
    require(is_hash(reference['sha256']), f'{label}: SHA-256 required')
    require(isinstance(relative, str) and relative and '\\' not in relative,
            f'{label}: relative path required')
    path = Path(relative)
    require(not path.is_absolute() and all(part not in ('', '.', '..') for part in path.parts),
            f'{label}: unsafe path')
    root = manifest_dir.resolve()
    target = manifest_dir / path
    require(target.resolve().is_relative_to(root) and target.is_file() and not target.is_symlink(),
            f'{label}: missing or unsafe evidence file')
    require(target.stat().st_size <= MAX_EVIDENCE_BYTES, f'{label}: evidence file too large')
    data = target.read_bytes()
    require(digest(data) == reference['sha256'], f'{label}: evidence bytes changed')
    return target, data


def proof_json(manifest_dir: Path, reference: object, label: str) -> dict:
    _, raw = evidence_file(manifest_dir, reference, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f'{label}: proof is not valid JSON') from None
    require(isinstance(value, dict), f'{label}: proof must be a JSON object')
    return value


def task_identity(row: object, label: str) -> dict:
    row = exact(row, {'task_id', 'package_sha256', 'source_groups',
                      'template_group', 'instance_group'}, label)
    require(is_task_id(row['task_id']) and is_hash(row['package_sha256']),
            f'{label}: invalid task identity or package hash')
    sources = row['source_groups']
    require(isinstance(sources, list) and sources and
            all(isinstance(item, str) and item.strip() == item and item for item in sources) and
            len(sources) == len(set(sources)), f'{label}: source groups required and unique')
    require(all(isinstance(row[key], str) and row[key].strip() == row[key] and row[key]
                for key in ('template_group', 'instance_group')),
            f'{label}: template and instance groups required')
    return row


def validate_splits(task_sets: object) -> list[dict]:
    task_sets = exact(task_sets, {'train', 'selection', 'official'}, 'task_sets')
    require(all(isinstance(task_sets[key], list) for key in task_sets), 'task sets must be lists')
    require(task_sets['selection'], 'selection task identities required')
    require(len(task_sets['official']) == 100, 'exactly 100 official tasks required')
    seen = {key: set() for key in ('task_id', 'package_sha256')}
    group_owners: dict[tuple[str, str], str] = {}
    official_instances: set[str] = set()
    for split, rows in task_sets.items():
        for index, raw in enumerate(rows):
            row = task_identity(raw, f'{split}[{index}]')
            for key in seen:
                require(row[key] not in seen[key], f'duplicate {key} across task sets')
                seen[key].add(row[key])
            groups = [('source', item) for item in row['source_groups']]
            groups += [('template', row['template_group']), ('instance', row['instance_group'])]
            if split == 'official':
                require(row['instance_group'] not in official_instances,
                        'official instances must be distinct')
                official_instances.add(row['instance_group'])
            for group in groups:
                owner = group_owners.get(group)
                require(owner is None or owner == split,
                        f'{group[0]} group leaked across splits: {group[1]}')
                group_owners[group] = split
    return task_sets['official']


def validate_qualification(evidence: object, manifest: dict, official: list[dict],
                           manifest_dir: Path) -> None:
    evidence = exact(evidence, {'schema', 'cell_id', 'status', 'bindings',
                                'cell_gates', 'official_tasks'},
                     'qualification evidence')
    require(evidence['schema'] == EVIDENCE_SCHEMA and evidence['cell_id'] == manifest['cell_id']
            and evidence['status'] == 'qualified', 'cell qualification evidence is not qualified')
    expected_bindings = {key + '_sha256': manifest['bindings'][key]['sha256']
                         for key in ('source_snapshot', 'runtime', 'action_contract', 'verifier')}
    require(evidence['bindings'] == expected_bindings,
            'qualification evidence differs from source/runtime/action/verifier bindings')
    gates = exact(evidence['cell_gates'], {'application_access', 'software_entitlement',
                                           'student_observation_and_sampling'}, 'cell gates')
    for gate, raw in gates.items():
        record = exact(raw, {'passed', 'evidence'}, gate + ' gate')
        require(record['passed'] is True, f'{gate}: cell is not qualified')
        receipt = proof_json(manifest_dir, record['evidence'], gate + ' gate')
        require(receipt == {'schema': 'cua-cell-gate-proof-v0.6',
                            'cell_id': manifest['cell_id'], 'gate': gate, 'passed': True},
                f'{gate}: cell qualification receipt differs')
    rows = evidence['official_tasks']
    require(isinstance(rows, list) and len(rows) == 100,
            'qualification evidence must cover all 100 official tasks')
    expected = {(row['task_id'], row['package_sha256']) for row in official}
    observed = set()
    for index, raw in enumerate(rows):
        row = exact(raw, {'task_id', 'package_sha256', 'build_passed', 'gui_roundtrip_passed',
                          'reset', 'independent_verifier'}, f'qualification[{index}]')
        identity = (row['task_id'], row['package_sha256'])
        require(identity in expected and identity not in observed,
                'qualification task identity/package missing or duplicate')
        observed.add(identity)
        require(row['build_passed'] is True and row['gui_roundtrip_passed'] is True,
                'official task lacks build or GUI save/readback proof')
        reset = exact(row['reset'], {'passed', 'evidence'}, 'reset proof')
        require(reset['passed'] is True,
                'official task lacks reset proof')
        reset_receipt = exact(proof_json(manifest_dir, reset['evidence'], 'reset proof'),
                              {'schema', 'task_id', 'package_sha256', 'initial_state_sha256',
                               'mutated_state_sha256', 'restored_state_sha256',
                               'fresh_environment', 'passed'}, 'reset proof receipt')
        require(reset_receipt['schema'] == 'cua-task-reset-proof-v0.6' and
                (reset_receipt['task_id'], reset_receipt['package_sha256']) == identity and
                reset_receipt['fresh_environment'] is True and reset_receipt['passed'] is True and
                all(is_hash(reset_receipt[key]) for key in ('initial_state_sha256',
                    'mutated_state_sha256', 'restored_state_sha256')) and
                reset_receipt['initial_state_sha256'] != reset_receipt['mutated_state_sha256'] and
                reset_receipt['initial_state_sha256'] == reset_receipt['restored_state_sha256'],
                'official task reset proof does not show mutation and restoration')
        verifier = exact(row['independent_verifier'],
                         {'separate_evaluator', 'positive_passed', 'negative_rejected',
                          'no_regression_checked', 'evidence'}, 'verifier proof')
        require(all(verifier[key] is True for key in ('separate_evaluator', 'positive_passed',
                    'negative_rejected', 'no_regression_checked')),
                'official task lacks independent positive/negative/no-regression verifier proof')
        verifier_receipt = exact(proof_json(manifest_dir, verifier['evidence'], 'verifier proof'),
                                 {'schema', 'task_id', 'package_sha256', 'evaluator_isolated',
                                  'positive_accepted', 'negative_rejected',
                                  'unrelated_changes_rejected', 'passed'}, 'verifier proof receipt')
        require(verifier_receipt == {
                    'schema': 'cua-task-verifier-proof-v0.6', 'task_id': identity[0],
                    'package_sha256': identity[1], 'evaluator_isolated': True,
                    'positive_accepted': True, 'negative_rejected': True,
                    'unrelated_changes_rejected': True, 'passed': True},
                'official task independent verifier proof does not pass')
    require(observed == expected, 'qualification task coverage differs from official manifest')


def validate_manifest(manifest: object, manifest_dir: Path) -> tuple[list[dict], Decimal, dict]:
    manifest = exact(manifest, {'schema', 'cell_id', 'researcher_id', 'role',
                                'qualification_status', 'task_sets', 'qualification_evidence',
                                'bindings', 'sampling', 'execution', 'cost'}, 'manifest')
    require(manifest['schema'] == MANIFEST_SCHEMA and is_slug(manifest['cell_id']) and
            is_slug(manifest['researcher_id']) and manifest['role'] in ('base', 'selected'),
            'invalid v0.6 cell/slot identity')
    require(manifest['qualification_status'] == 'qualified', 'cell is not qualified')
    official = validate_splits(manifest['task_sets'])

    bindings = exact(manifest['bindings'], {'checkpoint', 'source_snapshot', 'runtime',
                                            'action_contract', 'verifier'}, 'bindings')
    for key in ('source_snapshot', 'runtime', 'action_contract', 'verifier'):
        evidence_file(manifest_dir, bindings[key], f'{key} binding')
    checkpoint = exact(bindings['checkpoint'], {'model', 'sha256', 'freeze_receipt'}, 'checkpoint')
    require(isinstance(checkpoint['model'], str) and checkpoint['model'].strip() == checkpoint['model']
            and checkpoint['model'] and is_hash(checkpoint['sha256']), 'checkpoint binding incomplete')
    _, freeze_bytes = evidence_file(manifest_dir, checkpoint['freeze_receipt'], 'checkpoint freeze')
    try:
        freeze = json.loads(freeze_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('checkpoint freeze is not valid JSON') from None
    exact(freeze, {'schema', 'cell_id', 'researcher_id', 'role', 'checkpoint_sha256',
                   'selection_frozen'}, 'checkpoint freeze')
    require(freeze == {'schema': FREEZE_SCHEMA, 'cell_id': manifest['cell_id'],
                       'researcher_id': manifest['researcher_id'], 'role': manifest['role'],
                       'checkpoint_sha256': checkpoint['sha256'], 'selection_frozen': True},
            'checkpoint selection not frozen for this slot')

    _, qualification_bytes = evidence_file(manifest_dir, manifest['qualification_evidence'],
                                           'qualification evidence')
    try:
        qualification = json.loads(qualification_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('qualification evidence is not valid JSON') from None
    validate_qualification(qualification, manifest, official, manifest_dir)

    sampling = exact(manifest['sampling'], {'seed', 'temperature', 'max_output_tokens'}, 'sampling')
    require(type(sampling['seed']) is int and 0 <= sampling['seed'] < 2**31,
            'sampling seed missing or invalid')
    require(amount(sampling['temperature'], 'temperature') <= 2,
            'sampling temperature exceeds bound')
    positive_integer(sampling['max_output_tokens'], 'max_output_tokens', 100_000)
    execution = exact(manifest['execution'], {'tasks_per_chunk', 'max_actions_per_task',
                                               'max_wall_seconds_per_task', 'max_active_chunks'},
                      'execution')
    positive_integer(execution['tasks_per_chunk'], 'tasks_per_chunk', 3)
    positive_integer(execution['max_actions_per_task'], 'max_actions_per_task', 10_000)
    positive_integer(execution['max_wall_seconds_per_task'], 'max_wall_seconds_per_task', 86_400)
    positive_integer(execution['max_active_chunks'], 'max_active_chunks', 10_000)

    cost = exact(manifest['cost'], {'currency', 'basis', 'task_usd_upper_bound',
                                    'chunk_usd_upper_bound', 'authorized_ceiling_usd',
                                    'available_balance_usd', 'spending_authorized_by_user'}, 'cost')
    require(cost['currency'] == 'USD' and cost['basis'] ==
            'all_in_including_provider_compute_inference_storage_and_licenses' and
            cost['spending_authorized_by_user'] is True,
            'all-in cost basis and user authorization required')
    per_task = amount(cost['task_usd_upper_bound'], 'task_usd_upper_bound', positive=True)
    per_chunk = amount(cost['chunk_usd_upper_bound'], 'chunk_usd_upper_bound')
    ceiling = amount(cost['authorized_ceiling_usd'], 'authorized_ceiling_usd', positive=True)
    available = amount(cost['available_balance_usd'], 'available_balance_usd', positive=True)
    chunk_count = (100 + execution['tasks_per_chunk'] - 1) // execution['tasks_per_chunk']
    maximum = 100 * per_task + chunk_count * per_chunk
    require(maximum <= ceiling and maximum <= available,
            'declared all-in cost bound exceeds authorized ceiling or available balance')
    return official, maximum, qualification


def make_plan(manifest: dict, manifest_sha256: str, official: list[dict],
              cost_upper_bound: Decimal) -> dict:
    chunk_size = manifest['execution']['tasks_per_chunk']
    bindings = {key: manifest['bindings'][key]['sha256']
                for key in ('source_snapshot', 'runtime', 'action_contract', 'verifier')}
    bindings['checkpoint'] = manifest['bindings']['checkpoint']['sha256']
    bindings['checkpoint_model'] = manifest['bindings']['checkpoint']['model']
    chunks = []
    for offset in range(0, len(official), chunk_size):
        tasks = [{'task_id': row['task_id'], 'package_sha256': row['package_sha256']}
                 for row in official[offset:offset + chunk_size]]
        index = offset // chunk_size
        identity = {'manifest_sha256': manifest_sha256, 'index': index,
                    'tasks': tasks, 'bindings': bindings, 'sampling': manifest['sampling']}
        chunks.append({'chunk_id': (f'{manifest["cell_id"]}-{manifest["researcher_id"]}-'
                                    f'{manifest["role"]}-official-{index:03d}'),
                       'request_id': digest(json_bytes(identity)), 'task_count': len(tasks),
                       'tasks': tasks})
    return {'schema': PLAN_SCHEMA, 'cell_id': manifest['cell_id'],
            'researcher_id': manifest['researcher_id'], 'role': manifest['role'],
            'manifest_sha256': manifest_sha256,
            'qualification_evidence_sha256': manifest['qualification_evidence']['sha256'],
            'checkpoint_freeze_sha256': manifest['bindings']['checkpoint']['freeze_receipt']['sha256'],
            'bindings': bindings, 'sampling': manifest['sampling'],
            'execution': manifest['execution'], 'official_task_count': 100,
            'official_cluster_counts': {
                'source_groups': len({group for row in official for group in row['source_groups']}),
                'template_groups': len({row['template_group'] for row in official}),
                'instance_groups': len({row['instance_group'] for row in official}),
            },
            'one_hundred_independent_source_families_claimed': False,
            'chunk_count': len(chunks), 'chunks': chunks,
            'declared_all_in_cost_upper_bound_usd': str(cost_upper_bound),
            'cost_bound_is_declaration_not_invoice': True,
            'provider_dispatch_enabled': False, 'scores_present': False}


def atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(mode='wb', dir=path.parent, prefix='.' + path.name + '-',
                                     delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(manifest_path: str | Path, out_dir: str | Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('cell manifest is not valid JSON') from None
    official, maximum, _ = validate_manifest(manifest, manifest_path.parent)
    plan = make_plan(manifest, digest(raw), official, maximum)
    plan_bytes = json_bytes(plan)
    identity = {'schema': INTENT_SCHEMA, 'cell_id': manifest['cell_id'],
                'researcher_id': manifest['researcher_id'], 'role': manifest['role'],
                'manifest_sha256': digest(raw), 'plan_sha256': digest(plan_bytes),
                'qualification_evidence_sha256': manifest['qualification_evidence']['sha256'],
                'checkpoint_freeze_sha256': manifest['bindings']['checkpoint']['freeze_receipt']['sha256'],
                'chunk_request_ids': [chunk['request_id'] for chunk in plan['chunks']],
                'provider_dispatch_enabled': False, 'scores_present': False}
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    require(not out_dir.is_symlink(), 'output directory must not be a symlink')
    lock_path = out_dir.parent / ('.' + out_dir.name + '.prepare.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if out_dir.exists():
            require(out_dir.is_dir(), 'output path is not a directory')
        else:
            out_dir.mkdir()
        intent_path, plan_path = out_dir / 'intent.json', out_dir / 'chunk-plan.json'
        if intent_path.exists():
            require(intent_path.read_bytes() == json_bytes(identity),
                    'existing preparation intent differs from qualified manifest')
        else:
            require(not any(out_dir.iterdir()), 'unowned output exists without preparation intent')
            atomic_write(intent_path, json_bytes(identity))
        if plan_path.exists():
            require(plan_path.read_bytes() == plan_bytes, 'existing chunk plan changed')
        else:
            require(set(out_dir.iterdir()) == {intent_path}, 'partial output contains unexpected files')
            atomic_write(plan_path, plan_bytes)
        require(digest(plan_path.read_bytes()) == identity['plan_sha256'], 'persisted plan hash mismatch')
    return {'state': 'prepared_offline', 'cell_id': manifest['cell_id'],
            'researcher_id': manifest['researcher_id'], 'role': manifest['role'],
            'official_task_count': 100, 'chunk_count': len(plan['chunks']),
            'tail_task_count': plan['chunks'][-1]['task_count'],
            'intent_path': str(intent_path), 'chunk_plan_path': str(plan_path),
            'manifest_sha256': identity['manifest_sha256'],
            'declared_all_in_cost_upper_bound_usd': str(maximum),
            'provider_calls': 0, 'scores_present': False}
