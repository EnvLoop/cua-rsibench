"""Freeze the six admitted cells before any of the 24 data-research campaigns.

The post-campaign matrix requires selected checkpoints, which do not yet exist
at this stage. This offline gate binds the common task/runtime/model/budget
contract first. It performs no provider, application, or model work.
"""

from __future__ import annotations

from decimal import Decimal
import fcntl
import json
from pathlib import Path

from . import full_study_matrix_v1 as matrix
from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-pre-campaign-v1'
PLAN_SCHEMA = 'cua-full-study-pre-campaign-plan-v1'
INTENT_SCHEMA = 'cua-full-study-pre-campaign-intent-v1'


def build(manifest: object, root: Path, manifest_sha256: str) -> dict:
    manifest = cell_final.exact(manifest, {
        'schema', 'study_id', 'student_model', 'teacher_model',
        'researchers', 'configurations', 'cells', 'budget',
    }, 'pre-campaign protocol')
    cell_final.require(manifest['schema'] == SCHEMA and
                       cell_final.is_slug(manifest['study_id']) and
                       manifest['student_model'] == matrix.STUDENT and
                       manifest['teacher_model'] == matrix.TEACHER and
                       manifest['researchers'] == matrix.RESEARCHERS,
                       'pre-campaign schema, ID, or model roster changed')
    configs = cell_final.exact(manifest['configurations'],
                               {'student', 'teacher', 'researchers'},
                               'model configuration bindings')
    researcher_configs = cell_final.exact(configs['researchers'],
                                          set(matrix.RESEARCHERS),
                                          'researcher configuration bindings')
    frozen_configs = {
        'student': matrix._configuration(root, configs['student'],
                                          role='student', model=matrix.STUDENT),
        'teacher': matrix._configuration(root, configs['teacher'],
                                          role='teacher', model=matrix.TEACHER),
        'researchers': {key: matrix._configuration(
            root, researcher_configs[key], role='researcher',
            model=matrix.RESEARCHERS[key]) for key in matrix.RESEARCHERS},
    }
    limits = matrix._budget(manifest['budget'])
    cells = manifest['cells']
    cell_final.require(isinstance(cells, list) and len(cells) == len(matrix.CELLS),
                       'exactly six pre-campaign cells required')
    seen_cells: set[str] = set()
    seen_official_ids: set[str] = set()
    output_cells = []
    campaign_intents = []
    shared_base_upper = Decimal(0)
    for raw in cells:
        cell = cell_final.exact(raw, {'cell_id', 'analysis_families',
                                      'base_manifest'}, 'pre-campaign cell')
        cell_id = cell['cell_id']
        cell_final.require(cell_id in matrix.CELLS and cell_id not in seen_cells,
                           'missing, duplicate, or undeclared pre-campaign cell')
        seen_cells.add(cell_id)
        base = matrix._slot(root, cell['base_manifest'], cell_id=cell_id,
                            researcher_id='shared-base', role='base')
        identities = {row['task_id'] for row in base['official']}
        cell_final.require(len(identities) == matrix.OFFICIAL_PER_CELL and
                           not identities.intersection(seen_official_ids),
                           'official task identity repeated across cells')
        seen_official_ids.update(identities)
        family_binding, family_sha256, _ = matrix._json_reference(
            root, cell['analysis_families'], f'{cell_id} analysis families')
        family_binding = cell_final.exact(family_binding,
                                          {'schema', 'cell_id', 'family_by_task'},
                                          f'{cell_id} analysis families')
        families = family_binding['family_by_task']
        cell_final.require(family_binding['schema'] == 'cua-cell-analysis-families-v1' and
                           family_binding['cell_id'] == cell_id and
                           isinstance(families, dict) and set(families) == identities and
                           all(families[row['task_id']] in row['source_groups']
                               for row in base['official']),
                           f'{cell_id}: analysis family is missing or not a source group')
        cell_final.require(
            matrix.TINKER_USD_PER_CAMPAIGN + limits['researcher_inference'] +
            limits['teacher_usd'] + limits['e2b_usd'] +
            limits['storage_application_usd'] +
            base['cost_maximum'] <= limits['campaign_all_in'],
            f'{cell_id}: campaign cap omits selected final-evaluation reservation')
        shared_base_upper += base['cost_maximum']
        train_sha = cell_final.digest(cell_final.json_bytes(base['train']))
        selection_sha = cell_final.digest(cell_final.json_bytes(base['selection']))
        official_sha = cell_final.digest(cell_final.json_bytes(base['official']))
        output_cells.append({
            'cell_id': cell_id,
            'base_manifest_sha256': base['manifest_sha256'],
            'base_checkpoint_sha256': base['plan']['bindings']['checkpoint'],
            'qualification_sha256': base['qualification_sha256'],
            'analysis_family_sha256': family_sha256,
            'analysis_family_count': len(set(families.values())),
            'train_task_count': len(base['train']),
            'selection_task_count': matrix.SELECTION_PER_CELL,
            'official_task_count': matrix.OFFICIAL_PER_CELL,
            'train_identities_sha256': train_sha,
            'selection_identities_sha256': selection_sha,
            'official_identities_sha256': official_sha,
            'matched_bindings': base['matched_bindings'],
            'sampling': base['sampling'],
            'execution': base['execution'],
            'selected_final_cost_upper_bound_usd': str(base['cost_maximum']),
        })
        for researcher_id, researcher_model in matrix.RESEARCHERS.items():
            campaign = {
                'schema': 'cua-full-study-campaign-intent-v1',
                'study_id': manifest['study_id'], 'cell_id': cell_id,
                'researcher_id': researcher_id,
                'researcher_model': researcher_model,
                'protocol_manifest_sha256': manifest_sha256,
                'base_manifest_sha256': base['manifest_sha256'],
                'base_checkpoint_sha256': base['plan']['bindings']['checkpoint'],
                'qualification_sha256': base['qualification_sha256'],
                'train_identities_sha256': train_sha,
                'selection_identities_sha256': selection_sha,
                'official_identities_sha256': official_sha,
                'analysis_family_sha256': family_sha256,
                'matched_bindings': base['matched_bindings'],
                'student_config_sha256': frozen_configs['student']['config_sha256'],
                'teacher_config_sha256': frozen_configs['teacher']['config_sha256'],
                'researcher_config_sha256': frozen_configs['researchers'][researcher_id]['config_sha256'],
                'campaign_hours_cap': matrix.CAMPAIGN_HOURS,
                'tinker_usd_cap': str(matrix.TINKER_USD_PER_CAMPAIGN),
                'researcher_inference_usd_cap': str(limits['researcher_inference']),
                'teacher_rollout_usd_cap': str(limits['teacher_usd']),
                'e2b_usd_cap': str(limits['e2b_usd']),
                'storage_application_usd_cap': str(limits['storage_application_usd']),
                'e2b_sandbox_hours_cap': str(limits['e2b_hours']),
                'all_in_ceiling_usd': str(limits['campaign_all_in']),
                'matched_count_caps': {key: limits['raw'][key]
                                       for key in limits['bounded_counts']},
                'selected_checkpoint_known': False,
                'provider_dispatch_enabled': False,
            }
            campaign_intents.append({**campaign, 'intent_sha256':
                                     cell_final.digest(cell_final.json_bytes(campaign))})
    cell_final.require(seen_cells == set(matrix.CELLS) and
                       len(seen_official_ids) == 600,
                       'six declared cells or 600 unique official identities missing')
    campaign_reservation = limits['campaign_all_in'] * len(campaign_intents)
    study_upper = shared_base_upper + campaign_reservation
    cell_final.require(study_upper <= limits['global_ceiling'] and
                       study_upper <= limits['available'],
                       'pre-campaign all-in upper bound exceeds ceiling or available balance')
    output_cells.sort(key=lambda item: matrix.CELLS.index(item['cell_id']))
    campaign_intents.sort(key=lambda item: (matrix.CELLS.index(item['cell_id']),
                                            list(matrix.RESEARCHERS).index(item['researcher_id'])))
    return {
        'schema': PLAN_SCHEMA, 'study_id': manifest['study_id'],
        'protocol_manifest_sha256': manifest_sha256,
        'student_model': matrix.STUDENT, 'teacher_model': matrix.TEACHER,
        'researchers': matrix.RESEARCHERS,
        'configuration_bindings': frozen_configs,
        'cell_ids': list(matrix.CELLS),
        'campaign_count': len(campaign_intents),
        'distinct_official_task_identities': len(seen_official_ids),
        'selection_task_identities_per_cell': matrix.SELECTION_PER_CELL,
        'declared_shared_base_cost_upper_bound_usd': str(shared_base_upper),
        'declared_campaign_reservation_usd': str(campaign_reservation),
        'declared_all_in_cost_upper_bound_usd': str(study_upper),
        'cost_bound_is_declaration_not_invoice': True,
        'cells': output_cells, 'campaign_intents': campaign_intents,
        'provider_dispatch_enabled': False, 'scores_present': False,
    }


def prepare(manifest_path: str | Path, out_dir: str | Path) -> dict:
    manifest_path = Path(manifest_path).resolve()
    raw = manifest_path.read_bytes()
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError('pre-campaign manifest is not valid JSON') from None
    plan = build(manifest, manifest_path.parent, cell_final.digest(raw))
    plan_bytes = cell_final.json_bytes(plan)
    intent = {
        'schema': INTENT_SCHEMA, 'study_id': plan['study_id'],
        'protocol_manifest_sha256': plan['protocol_manifest_sha256'],
        'plan_sha256': cell_final.digest(plan_bytes),
        'campaign_intent_sha256': [row['intent_sha256'] for row in plan['campaign_intents']],
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
        intent_path, plan_path = out_dir / 'intent.json', out_dir / 'campaign-plan.json'
        if intent_path.exists():
            cell_final.require(intent_path.read_bytes() == cell_final.json_bytes(intent),
                               'existing pre-campaign intent differs')
        else:
            cell_final.require(not any(out_dir.iterdir()),
                               'unowned output exists without pre-campaign intent')
            cell_final.atomic_write(intent_path, cell_final.json_bytes(intent))
        if plan_path.exists():
            cell_final.require(plan_path.read_bytes() == plan_bytes,
                               'existing pre-campaign plan changed')
        else:
            cell_final.require(set(out_dir.iterdir()) == {intent_path},
                               'partial pre-campaign output contains unexpected files')
            cell_final.atomic_write(plan_path, plan_bytes)
        cell_final.require(cell_final.digest(plan_path.read_bytes()) == intent['plan_sha256'],
                           'persisted pre-campaign plan hash mismatch')
    return {
        'state': 'prepared_offline', 'study_id': plan['study_id'],
        'campaign_count': plan['campaign_count'],
        'distinct_official_task_identities': plan['distinct_official_task_identities'],
        'declared_all_in_cost_upper_bound_usd': plan['declared_all_in_cost_upper_bound_usd'],
        'intent_path': str(intent_path), 'campaign_plan_path': str(plan_path),
        'provider_calls': 0, 'scores_present': False,
    }
