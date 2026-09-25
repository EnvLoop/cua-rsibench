"""Replay the admitted quarantined Magento v1 episode into cell-neutral v2.

The source GUI trace and public qualification are immutable inputs. This tool
copies original masked frames and action JSON without alteration, normalizes
independent verifier receipts, and converts a provisional 20/100 candidate
plan into explicit selection/final manifests. No model or GUI call occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from cursibench.gui_sft_data_v1 import validate_episode as validate_v1
from cursibench.gui_sft_episode_v2 import (
    ACTION_VERSION, GATE_SCHEMA, MODEL, PROCESSOR, RENDERER, SCHEMA,
    SPLIT_SCHEMA, _source_binding, json_text, sha256, validate_episode,
)


ROOT = Path(__file__).resolve().parents[1]
V1_EPISODE_SHA256 = '8ae9143ab98ea96572a19c3e5cd4a8a529f5dc320cb61044a57acddc2c5b22f0'
SOURCE_REVISION = '6473f72db5dcefc97b5725b59e734504edc28a21'
DATASET_SHA256 = 'd65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30'
TASK_SHA256 = 'a39bdffcb64ffc8cbb5305858853c6c87664eac0060fedfd554b5bf6bfe9f177'
TASK_ID = '777'
TEMPLATE_ID = '742'
ENTITY_TAGS = [f'magento:product:{value}' for value in (111, 114, 117, 120, 123)]


def require(value, code):
    if not value:
        raise ValueError(code)


def write_new(path: Path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
    path.chmod(0o600)


def _entity_hint(value: str) -> str:
    if value.startswith('product_id:') and value[11:].isdigit():
        return 'magento:product:' + value[11:]
    if value.startswith('order_id:') and value[9:].isdigit():
        return 'magento:order:' + value[9:]
    if value.startswith('order:') and value[6:].isdigit():
        return 'magento:order:' + value[6:]
    # Opaque names/phone hints remain comparable by exact source text without
    # leaking that text or claiming a database-identity join.
    require(type(value) is str and value, 'invalid_magento_entity_hint')
    return 'magento:hint:' + sha256(value.encode())[:32]


def candidate_manifests(plan: dict, plan_sha256: str) -> tuple[dict, dict]:
    require(plan.get('schema') == 'cua-magento-admission-backlog-v0.6' and
            plan.get('source', {}).get('commit') == SOURCE_REVISION and
            plan['source'].get('dataset_sha256') == DATASET_SHA256 and
            TASK_ID in {str(value) for value in
                        plan.get('quarantine', {}).get('train_reserved_task_ids', [])} and
            742 in plan['quarantine']['template_ids'],
            'candidate_plan_not_quarantined')
    result = []
    for split, key, count in (('selection', 'selection', 20),
                              ('final', 'provisional_final', 100)):
        source_rows = plan.get('task_sets', {}).get(key)
        require(type(source_rows) is list and len(source_rows) == count,
                'candidate_plan_count_changed')
        rows = []
        for item in source_rows:
            group = item['template_group']
            require(group.startswith('shopping_admin:') and
                    group.rsplit(':', 1)[-1].isdigit(), 'invalid_source_template')
            rows.append({
                'task_id': str(item['task_id']),
                'template_id': group.rsplit(':', 1)[-1],
                'entity_tags': sorted({_entity_hint(hint)
                                       for hint in item['source_entity_hints']}),
            })
        result.append({
            'schema': SPLIT_SCHEMA, 'cell': 'magento_admin', 'split': split,
            'source_name': 'WebArena-Verified',
            'source_revision': SOURCE_REVISION,
            'source_dataset_sha256': DATASET_SHA256,
            'status': 'provisional',
            'entity_coverage': 'declared_hints_only',
            'source_plan_sha256': plan_sha256,
            'items': rows,
        })
    return tuple(result)


def gate_receipts(source: dict, result: dict, v1: dict,
                  qualification: dict, source_result_sha256: str,
                  qualification_sha256: str) -> dict[str, dict]:
    base = {'schema': GATE_SCHEMA, 'cell': 'magento_admin',
            'source_binding_sha256': _source_binding(source, 'magento_admin'),
            'status': 'pass', 'independent_of_actor': True}
    admission = v1['admission']
    require(admission['published_evaluator_score'] == 1.0 and
            admission['raw_and_sanitized_evaluator_equal'] is True and
            result['independent_saved_state_pass'] is True and
            result['final_reset_verified'] is True and
            qualification['source']['task_sha256'] == TASK_SHA256 and
            qualification['task_id'] == 777 and
            qualification['negative']['published_evaluator_score'] == 0.0 and
            qualification['negative']['independent_sql_wrong_object_pass'] is True and
            qualification['positive']['independent_sql_persisted_state_pass'] is True and
            qualification['reset']['selected_sql_rows_match_baseline_after_each_case'] is True and
            qualification['reset']['sql_monitored_tables_match_baseline_after_each_case'] is True and
            qualification['reset']['complete_search_documents_match_baseline_after_each_case'] is True,
            'magento_independent_controls_not_qualified')
    before_search = qualification['reset']['search_index_before_sha256']
    restored_search = qualification['reset']['search_index_restored_after_positive_sha256']
    require(before_search == restored_search, 'search_reset_hash_mismatch')
    return {
        'positive': {**base, 'gate': 'positive',
                     'verifier_kind': 'published_evaluator', 'score': 1.0,
                     'source_artifact_path': 'receipts/source-result.json',
                     'source_artifact_sha256': source_result_sha256},
        'negative': {**base, 'gate': 'negative',
                     'verifier_kind': 'negative_control', 'score': 0.0,
                     'control_kind': 'wrong_object',
                     'independent_state_control_pass': True,
                     'source_artifact_path': 'receipts/source-qualification.json',
                     'source_artifact_sha256': qualification_sha256},
        'saved_state': {**base, 'gate': 'saved_state',
                        'verifier_kind': 'independent_readback',
                        'target_state_pass': True,
                        'unintended_state_preserved': True,
                        'source_artifact_path': 'receipts/source-result.json',
                        'source_artifact_sha256': source_result_sha256},
        'reset': {**base, 'gate': 'reset',
                  'verifier_kind': 'state_equivalence',
                  'state_equivalence_pass': True,
                  'baseline_semantic_sha256': before_search,
                  'restored_semantic_sha256': restored_search,
                  'business_state_rows_match_baseline': True,
                  'source_artifact_path': 'receipts/source-qualification.json',
                  'source_artifact_sha256': qualification_sha256},
    }


def convert(v1_dir: Path, qualification_path: Path, candidate_plan_path: Path,
            out: Path) -> dict:
    v1_dir, out = Path(v1_dir).resolve(), Path(out).resolve()
    require(not out.exists() and out.is_relative_to(ROOT / 'work'),
            'fresh_private_output_required')
    v1_bytes = (v1_dir / 'episode.json').read_bytes()
    require(sha256(v1_bytes) == V1_EPISODE_SHA256,
            'v1_episode_identity_changed')
    v1, v1_turns = validate_v1(v1_dir)
    source_result_bytes = (v1_dir / 'result.json').read_bytes()
    result = json.loads(source_result_bytes)
    require(v1['task_id'] == 777 and v1['intent_template_id'] == 742 and
            result['status'] == 'completed' and result['official_score'] == 1.0 and
            result['paid_provider_calls'] == 0 and len(v1_turns) == 36,
            'v1_training_episode_not_admitted')
    qualification_bytes = Path(qualification_path).read_bytes()
    qualification = json.loads(qualification_bytes)
    plan_bytes = Path(candidate_plan_path).read_bytes()
    manifests = candidate_manifests(json.loads(plan_bytes), sha256(plan_bytes))
    source = {
        'name': 'WebArena-Verified', 'revision': SOURCE_REVISION,
        'dataset_sha256': DATASET_SHA256, 'task_id': TASK_ID,
        'template_id': TEMPLATE_ID, 'task_sha256': TASK_SHA256,
        'entity_tags': ENTITY_TAGS,
        'observation_task_id': 'webarena.shopping_admin.777',
    }
    gates = gate_receipts(source, result, v1, qualification,
                          sha256(source_result_bytes), sha256(qualification_bytes))
    out.mkdir(mode=0o700, parents=True)
    (out / 'frames').mkdir(mode=0o700)
    (out / 'receipts').mkdir(mode=0o700)
    for name, raw in (('source-result.json', source_result_bytes),
                      ('source-qualification.json', qualification_bytes)):
        path = out / 'receipts' / name
        path.write_bytes(raw)
        path.chmod(0o600)
    refs = {}
    for name, receipt in gates.items():
        relative = f'receipts/{name}.json'
        write_new(out / relative, receipt)
        refs[name] = {'path': relative, 'sha256': sha256((out / relative).read_bytes())}
    write_new(out / 'selection.json', manifests[0])
    write_new(out / 'final.json', manifests[1])
    for index, step in enumerate(v1['steps']):
        relative = f'frames/step-{index:03d}.png'
        require(step['screenshot_file'] == relative,
                'v1_frame_name_changed')
        raw = (v1_dir / relative).read_bytes()
        require(sha256(raw) == step['screenshot_sha256'],
                'v1_frame_bytes_changed')
        path = out / relative
        shutil.copyfile(v1_dir / relative, path)
        path.chmod(0o600)
    episode = {
        'schema': SCHEMA, 'split': 'train', 'cell': 'magento_admin',
        'source': source, 'action_contract_version': ACTION_VERSION,
        'renderer': {'model': MODEL, 'name': RENDERER,
                     'image_processor': PROCESSOR},
        'provenance_receipts': refs,
        'steps': v1['steps'],
        'derivation': {
            'kind': 'schema_only_from_action_only_v1',
            'v1_episode_sha256': V1_EPISODE_SHA256,
            'v1_result_sha256': sha256(source_result_bytes),
            'qualification_sha256': sha256(qualification_bytes),
            'candidate_plan_sha256': sha256(plan_bytes),
            'executed_actions_and_masked_frames_unchanged': True,
        },
    }
    write_new(out / 'episode.json', episode)
    write_new(out / 'result.json', {
        'status': 'completed',
        'episode_sha256': sha256((out / 'episode.json').read_bytes()),
        'action_count': len(v1['steps']), 'frame_count': len(v1['steps']),
        'paid_provider_calls': 0,
        'derivation': episode['derivation'],
    })
    _, turns, proof = validate_episode(
        out, selection_manifest=out / 'selection.json',
        final_manifest=out / 'final.json')
    before_actions = [step['action'] for step in v1['steps']]
    after_actions = [turn['action'] for turn in turns]
    before_frames = [step['screenshot_sha256'] for step in v1['steps']]
    after_frames = [step['screenshot_sha256']
                    for step in json.loads((out / 'episode.json').read_text())['steps']]
    require(before_actions == after_actions and before_frames == after_frames,
            'v1_v2_actor_bytes_changed')
    return {
        'schema': 'gui-sft-v1-v2-replay-v1',
        'v1_episode_sha256': V1_EPISODE_SHA256,
        'v2_episode_sha256': proof['episode_sha256'],
        'action_sha256': proof['action_sha256'],
        'frame_sha256': proof['frame_sha256'],
        'action_and_frame_bytes_unchanged': True,
        'validated_turns': len(turns),
        'selection_candidates': proof['split']['selection_count'],
        'provisional_final_candidates': proof['split']['final_count'],
        'official_final_tasks_added': 0,
        'paid_provider_calls': 0,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-episode', type=Path, required=True)
    parser.add_argument('--qualification-receipt', type=Path, required=True)
    parser.add_argument('--candidate-plan', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(convert(args.v1_episode, args.qualification_receipt,
                             args.candidate_plan, args.out), sort_keys=True))
