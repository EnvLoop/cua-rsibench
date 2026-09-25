"""Export allowlisted v2 replay evidence without actor frames or oracle data."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench.gui_sft_episode_v2 import (
    COOKBOOK_COMMIT, MODEL, PROCESSOR, RENDERER, sha256,
    validate_episode,
)


def receipt(root: Path, offline_path: Path) -> dict:
    root = Path(root).resolve()
    episode, turns, proof = validate_episode(
        root, selection_manifest=root / 'selection.json',
        final_manifest=root / 'final.json')
    offline_bytes = Path(offline_path).read_bytes()
    offline = json.loads(offline_bytes)
    if (offline.get('schema') != 'gui-sft-offline-render-v2' or
            offline.get('cell') != episode['cell'] or
            offline.get('source') != episode['source'] or
            offline.get('model') != MODEL or
            offline.get('renderer') != RENDERER or
            offline.get('image_processor') != PROCESSOR or
            offline.get('cookbook_commit') != COOKBOOK_COMMIT or
            offline.get('datum_count') != len(turns) or
            offline.get('provenance') != proof or
            offline.get('paid_provider_calls') != 0 or
            offline.get('optimizer_steps') != 0):
        raise ValueError('offline_render_receipt_mismatch')
    derivation = episode.get('derivation') or {}
    if (derivation.get('kind') != 'schema_only_from_action_only_v1' or
            derivation.get('executed_actions_and_masked_frames_unchanged') is not True):
        raise ValueError('actor_bytes_derivation_unverified')
    return {
        'schema': 'gui-sft-v2-public-replay-v1',
        'evidence_class': 'offline_cross_cell_contract_and_single_magento_replay',
        'supported_cell_identifiers': [
            'magento_admin', 'gitlab_project', 'odoo_erp',
            'office_excel_web', 'office_powerpoint_web', 'libreoffice_desktop',
        ],
        'replay': {
            'source_cell': episode['cell'],
            'source_name': episode['source']['name'],
            'source_revision': episode['source']['revision'],
            'source_dataset_sha256': episode['source']['dataset_sha256'],
            'source_task_id': episode['source']['task_id'],
            'source_template_id': episode['source']['template_id'],
            'v1_episode_sha256': derivation['v1_episode_sha256'],
            'v2_episode_sha256': proof['episode_sha256'],
            'unchanged_action_sha256': proof['action_sha256'],
            'unchanged_frame_sha256': proof['frame_sha256'],
            'validated_current_frame_actions': len(turns),
            'executed_actions_and_masked_frames_unchanged': True,
        },
        'provenance_gates': proof['gate_receipt_sha256'],
        'selection_final_exclusion': proof['split'],
        'offline_renderer': {
            'model': MODEL, 'renderer': RENDERER,
            'image_processor': PROCESSOR,
            'renderer_identity': offline['renderer_identity'],
            'cookbook_commit': COOKBOOK_COMMIT,
            'tinker_sdk_version': offline['tinker_sdk_version'],
            'image_plus_action_datums': offline['datum_count'],
            'max_supervised_tokens': offline['max_supervised_tokens'],
            'max_image_tokens': offline['max_image_tokens'],
            'minimum_positive_assistant_loss_sum':
                offline['minimum_positive_assistant_loss_sum'],
            'paid_provider_calls_in_v2_replay': 0,
            'optimizer_steps_in_v2_replay': 0,
        },
        'private_artifact_sha256': {
            'offline_render_receipt': sha256(offline_bytes),
            'source_qualification': derivation['qualification_sha256'],
            'candidate_plan': derivation['candidate_plan_sha256'],
        },
        'limits': {
            'selection_and_final_tasks_are_provisional': True,
            'entity_tags_cover_only_declared_source_hints': True,
            'other_cells_have_real_gui_episode_replays': False,
            'official_final_tasks_added': 0,
            'trained_improvement_measured_by_v2': False,
            'private_screenshots_or_oracle_payload_published': False,
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--offline-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    public = receipt(args.episode, args.offline_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(public, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'schema': public['schema'],
                      'replayed_actions': public['replay']['validated_current_frame_actions'],
                      'official_final_tasks_added': 0}, sort_keys=True))
