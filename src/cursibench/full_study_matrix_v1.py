"""Fail-closed offline preparation for a matched 4 x 6 computer-use study.

Every slot is revalidated against its evaluator-owned v0.6 cell manifest and
100 per-task admission receipts. This module schedules no provider or GUI work
and never creates a score. It only freezes a common matrix after all six cells
have passed their individual admission gates.
"""

from __future__ import annotations

from decimal import Decimal
import fcntl
import json
from pathlib import Path

from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-matrix-v1'
PLAN_SCHEMA = 'cua-full-study-offline-plan-v1'
INTENT_SCHEMA = 'cua-full-study-preparation-intent-v1'
STUDENT = 'Qwen/Qwen3.8-27B'
TEACHER = 'gpt-5.6-sol'
CELLS = (
    'powerpoint-web', 'excel-web', 'desktop-native',
    'servicenow', 'gitlab', 'magento-admin',
)
RESEARCHERS = {
    'astra': 'gpt-6-astra',
    'sol56': 'gpt-5.6-sol',
    'sol6': 'gpt-6-sol',
    'luna6': 'gpt-6-luna',
}
OFFICIAL_PER_CELL = 100
SELECTION_PER_CELL = 20
CAMPAIGN_HOURS = 16
TINKER_USD_PER_CAMPAIGN = Decimal('500')


def _json_reference(root: Path, reference: object, label: str) -> tuple[dict, str, Path]:
    path, raw = cell_final.evidence_file(root, reference, label)
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError(f'{label}: invalid JSON') from None
    cell_final.require(isinstance(value, dict), f'{label}: JSON object required')
    return value, cell_final.digest(raw), path


def _identities(rows: list[dict]) -> list[dict]:
    return [cell_final.task_identity(row, 'matrix task identity') for row in rows]


def _configuration(root: Path, reference: object, *, role: str,
                   model: str) -> dict:
    value, sha256, path = _json_reference(root, reference, f'{role} configuration')
    value = cell_final.exact(value, {'schema', 'role', 'model', 'snapshot_id',
                                     'settings', 'assets'}, f'{role} configuration')
    cell_final.require(value['schema'] == 'cua-model-configuration-v1' and
                       value['role'] == role and value['model'] == model,
                       f'{role}: configured model or role changed')
    cell_final.require(value['snapshot_id'] is None or
                       (isinstance(value['snapshot_id'], str) and
                        value['snapshot_id'].strip() == value['snapshot_id'] and
                        value['snapshot_id']),
                       f'{role}: invalid provider-reported snapshot identity')
    settings = value['settings']
    cell_final.require(isinstance(settings, dict) and settings,
                       f'{role}: settings required')
    needed = ({'renderer', 'image_processor', 'temperature', 'max_output_tokens'}
              if role == 'student' else
              {'reasoning_effort', 'temperature', 'max_output_tokens'})
    cell_final.require(needed <= set(settings) and
                       all(settings[key] is not None for key in needed),
                       f'{role}: required inference settings missing')
    asset_names = {'prompt', 'harness', 'tool_grammar', 'decoding', 'provider_route'}
    if role == 'student':
        asset_names.add('training')
    assets = cell_final.exact(value['assets'], asset_names, f'{role} assets')
    for name, asset in assets.items():
        cell_final.evidence_file(path.parent, asset, f'{role}/{name} asset')
    return {'config_sha256': sha256,
            'asset_sha256': {name: asset['sha256'] for name, asset in assets.items()},
            'snapshot_id': value['snapshot_id']}


def _slot(root: Path, reference: object, *, cell_id: str, researcher_id: str,
          role: str) -> dict:
    manifest, manifest_sha, path = _json_reference(
        root, reference, f'{cell_id}/{researcher_id}/{role} manifest')
    cell_final.require(manifest.get('cell_id') == cell_id and
                       manifest.get('researcher_id') == researcher_id and
                       manifest.get('role') == role,
                       f'{cell_id}: slot identity or role changed')
    cell_final.require(manifest.get('bindings', {}).get('checkpoint', {}).get('model') == STUDENT,
                       f'{cell_id}: student model differs from frozen roster')
    official, maximum, _ = cell_final.validate_manifest(manifest, path.parent)
    sets = manifest['task_sets']
    cell_final.require(len(sets['selection']) == SELECTION_PER_CELL and sets['train'],
                       f'{cell_id}: 20 selection identities and train sources required')
    plan = cell_final.make_plan(manifest, manifest_sha, official, maximum)
    return {
        'manifest_sha256': manifest_sha,
        'qualification_sha256': manifest['qualification_evidence']['sha256'],
        'official': _identities(official),
        'selection': _identities(sets['selection']),
        'train': _identities(sets['train']),
        'matched_bindings': {key: manifest['bindings'][key]['sha256']
                             for key in ('source_snapshot', 'runtime',
                                         'action_contract', 'verifier')},
        'sampling': manifest['sampling'],
        'execution': manifest['execution'],
        'cost_maximum': maximum,
        'plan': plan,
    }


def build(manifest: object, root: Path, manifest_sha256: str) -> dict:
    manifest = cell_final.exact(manifest, {
        'schema', 'study_id', 'student_model', 'teacher_model',
        'researchers', 'configurations', 'cells', 'budget',
    }, 'matrix')
    cell_final.require(manifest['schema'] == SCHEMA and
                       cell_final.is_slug(manifest['study_id']),
                       'invalid full-study schema or ID')
    cell_final.require(manifest['student_model'] == STUDENT and
                       manifest['teacher_model'] == TEACHER and
                       manifest['researchers'] == RESEARCHERS,
                       'student, teacher, or researcher roster changed')
    configs = cell_final.exact(manifest['configurations'],
                               {'student', 'teacher', 'researchers'},
                               'model configuration bindings')
    researcher_configs = cell_final.exact(configs['researchers'], set(RESEARCHERS),
                                          'researcher configuration bindings')
    frozen_configs = {
        'student': _configuration(root, configs['student'], role='student', model=STUDENT),
        'teacher': _configuration(root, configs['teacher'], role='teacher', model=TEACHER),
        'researchers': {key: _configuration(root, researcher_configs[key],
                                             role='researcher', model=RESEARCHERS[key])
                        for key in RESEARCHERS},
    }
    budget = cell_final.exact(manifest['budget'], {
        'campaign_hours', 'tinker_usd_per_campaign',
        'researcher_inference_usd_per_campaign', 'researcher_calls_per_campaign',
        'teacher_rollout_tokens_per_campaign', 'teacher_rollout_calls_per_campaign',
        'e2b_sandbox_hours_per_campaign', 'e2b_peak_concurrency',
        'candidate_submissions_per_campaign', 'selection_evaluations_per_campaign',
        'per_campaign_all_in_ceiling_usd',
        'global_all_in_ceiling_usd', 'available_all_in_usd',
        'spending_authorized_by_user',
    }, 'matrix budget')
    cell_final.require(budget['campaign_hours'] == CAMPAIGN_HOURS and
                       cell_final.amount(budget['tinker_usd_per_campaign'],
                                         'tinker_usd_per_campaign') == TINKER_USD_PER_CAMPAIGN and
                       budget['spending_authorized_by_user'] is True,
                       'per-campaign time, Tinker cap, or user authorization changed')
    global_ceiling = cell_final.amount(budget['global_all_in_ceiling_usd'],
                                       'global_all_in_ceiling_usd', positive=True)
    available = cell_final.amount(budget['available_all_in_usd'],
                                  'available_all_in_usd', positive=True)
    campaign_all_in = cell_final.amount(budget['per_campaign_all_in_ceiling_usd'],
                                        'per_campaign_all_in_ceiling_usd', positive=True)
    researcher_inference = cell_final.amount(
        budget['researcher_inference_usd_per_campaign'],
        'researcher_inference_usd_per_campaign', positive=True)
    e2b_hours = cell_final.amount(budget['e2b_sandbox_hours_per_campaign'],
                                  'e2b_sandbox_hours_per_campaign', positive=True)
    bounded_counts = (
        'researcher_calls_per_campaign', 'teacher_rollout_tokens_per_campaign',
        'teacher_rollout_calls_per_campaign', 'e2b_peak_concurrency',
        'candidate_submissions_per_campaign', 'selection_evaluations_per_campaign',
    )
    for key in bounded_counts:
        cell_final.positive_integer(budget[key], key)
    cells = manifest['cells']
    cell_final.require(isinstance(cells, list) and len(cells) == len(CELLS),
                       'exactly six cells required')
    seen: set[str] = set()
    output_cells = []
    all_in = Decimal(0)
    unique_final_executions = 0
    for raw in cells:
        cell = cell_final.exact(raw, {'cell_id', 'base_manifest',
                                     'selected_manifests'}, 'matrix cell')
        cell_id = cell['cell_id']
        cell_final.require(cell_id in CELLS and cell_id not in seen,
                           'missing, duplicate, or undeclared application cell')
        seen.add(cell_id)
        selected = cell_final.exact(cell['selected_manifests'], set(RESEARCHERS),
                                    f'{cell_id} researcher manifests')
        base = _slot(root, cell['base_manifest'], cell_id=cell_id,
                     researcher_id='shared-base', role='base')
        slots = {'shared-base': base}
        for researcher_id in RESEARCHERS:
            slots[researcher_id] = _slot(root, selected[researcher_id],
                                         cell_id=cell_id,
                                         researcher_id=researcher_id,
                                         role='selected')
        for researcher_id, slot in slots.items():
            cell_final.require(slot['official'] == base['official'] and
                               slot['selection'] == base['selection'] and
                               slot['train'] == base['train'],
                               f'{cell_id}/{researcher_id}: matched task identities differ')
            cell_final.require(slot['qualification_sha256'] == base['qualification_sha256'] and
                               slot['matched_bindings'] == base['matched_bindings'] and
                               slot['sampling'] == base['sampling'] and
                               slot['execution'] == base['execution'],
                               f'{cell_id}/{researcher_id}: matched environment or policy differs')
            all_in += slot['cost_maximum']
            if researcher_id != 'shared-base':
                cell_final.require(slot['cost_maximum'] <= campaign_all_in,
                                   f'{cell_id}/{researcher_id}: campaign all-in cap exceeded')
        execution_owners: dict[str, str] = {}
        reuse = {}
        for researcher_id in ('shared-base', *RESEARCHERS):
            checkpoint = slots[researcher_id]['plan']['bindings']['checkpoint']
            owner = execution_owners.setdefault(checkpoint, researcher_id)
            reuse[researcher_id] = owner
        unique_final_executions += len(execution_owners) * OFFICIAL_PER_CELL
        output_cells.append({
            'cell_id': cell_id,
            'official_task_count': OFFICIAL_PER_CELL,
            'selection_task_count': SELECTION_PER_CELL,
            'train_task_count': len(base['train']),
            'official_identities_sha256': cell_final.digest(cell_final.json_bytes(base['official'])),
            'qualification_sha256': base['qualification_sha256'],
            'matched_bindings': base['matched_bindings'],
            'unique_checkpoint_count': len(execution_owners),
            'execution_evidence_owner_by_slot': reuse,
            'base': base['plan'],
            'researcher_plans': {key: slots[key]['plan'] for key in RESEARCHERS},
        })
    cell_final.require(seen == set(CELLS), 'six declared cells not covered')
    cell_final.require(all_in <= global_ceiling and all_in <= available,
                       'matrix all-in upper bound exceeds declared ceiling or available balance')
    output_cells.sort(key=lambda item: CELLS.index(item['cell_id']))
    return {
        'schema': PLAN_SCHEMA, 'study_id': manifest['study_id'],
        'matrix_manifest_sha256': manifest_sha256,
        'student_model': STUDENT, 'teacher_model': TEACHER,
        'researchers': RESEARCHERS, 'configuration_bindings': frozen_configs,
        'cell_ids': list(CELLS),
        'campaign_count': len(CELLS) * len(RESEARCHERS),
        'shared_base_evaluation_count': len(CELLS),
        'distinct_official_task_identities': len(CELLS) * OFFICIAL_PER_CELL,
        'initial_base_final_trials': len(CELLS) * OFFICIAL_PER_CELL,
        'initial_selected_final_trials': len(CELLS) * len(RESEARCHERS) * OFFICIAL_PER_CELL,
        'initial_total_slot_task_results': len(CELLS) * (1 + len(RESEARCHERS)) * OFFICIAL_PER_CELL,
        'planned_unique_checkpoint_task_executions': unique_final_executions,
        'campaign_hours_cap': CAMPAIGN_HOURS,
        'tinker_usd_cap_per_campaign': str(TINKER_USD_PER_CAMPAIGN),
        'researcher_inference_usd_cap_per_campaign': str(researcher_inference),
        'e2b_sandbox_hours_cap_per_campaign': str(e2b_hours),
        'per_campaign_all_in_ceiling_usd': str(campaign_all_in),
        'matched_non_tinker_campaign_caps': {key: budget[key] for key in bounded_counts},
        'nominal_tinker_cap_all_campaigns_usd': str(
            TINKER_USD_PER_CAMPAIGN * len(CELLS) * len(RESEARCHERS)),
        'declared_all_in_cost_upper_bound_usd': str(all_in),
        'cost_bound_is_declaration_not_invoice': True,
        'cells': output_cells,
        'provider_dispatch_enabled': False, 'scores_present': False,
    }


def prepare(manifest_path: str | Path, out_dir: str | Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('matrix manifest is not valid JSON') from None
    plan = build(manifest, manifest_path.parent, cell_final.digest(raw))
    plan_bytes = cell_final.json_bytes(plan)
    intent = {
        'schema': INTENT_SCHEMA, 'study_id': plan['study_id'],
        'matrix_manifest_sha256': plan['matrix_manifest_sha256'],
        'plan_sha256': cell_final.digest(plan_bytes),
        'cell_ids': list(CELLS),
        'campaign_count': plan['campaign_count'],
        'provider_dispatch_enabled': False, 'scores_present': False,
    }
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    cell_final.require(not out_dir.is_symlink(), 'output directory must not be a symlink')
    lock_path = out_dir.parent / ('.' + out_dir.name + '.prepare.lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if out_dir.exists():
            cell_final.require(out_dir.is_dir(), 'output path is not a directory')
        else:
            out_dir.mkdir()
        intent_path, plan_path = out_dir / 'intent.json', out_dir / 'matrix-plan.json'
        if intent_path.exists():
            cell_final.require(intent_path.read_bytes() == cell_final.json_bytes(intent),
                               'existing matrix intent differs')
        else:
            cell_final.require(not any(out_dir.iterdir()),
                               'unowned output exists without matrix intent')
            cell_final.atomic_write(intent_path, cell_final.json_bytes(intent))
        if plan_path.exists():
            cell_final.require(plan_path.read_bytes() == plan_bytes,
                               'existing matrix plan changed')
        else:
            cell_final.require(set(out_dir.iterdir()) == {intent_path},
                               'partial matrix output contains unexpected files')
            cell_final.atomic_write(plan_path, plan_bytes)
        cell_final.require(cell_final.digest(plan_path.read_bytes()) == intent['plan_sha256'],
                           'persisted matrix plan hash mismatch')
    return {
        'state': 'prepared_offline', 'study_id': plan['study_id'],
        'campaign_count': plan['campaign_count'],
        'distinct_official_task_identities': plan['distinct_official_task_identities'],
        'initial_total_slot_task_results': plan['initial_total_slot_task_results'],
        'planned_unique_checkpoint_task_executions': plan['planned_unique_checkpoint_task_executions'],
        'intent_path': str(intent_path), 'matrix_plan_path': str(plan_path),
        'declared_all_in_cost_upper_bound_usd': plan['declared_all_in_cost_upper_bound_usd'],
        'provider_calls': 0, 'scores_present': False,
    }
