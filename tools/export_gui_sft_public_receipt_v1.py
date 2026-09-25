"""Export allowlisted public evidence from one private admitted GUI SFT episode."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from cursibench.gui_sft_data_v1 import (
    COOKBOOK_COMMIT, MODEL, PROCESSOR, RENDERER, TRAIN_TASK_ID,
    TRAIN_TEMPLATE_ID, train_exclusion_manifest, validate_episode,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_receipt(episode_dir: Path, offline_receipt: Path,
                   paid_receipt: Path | None = None) -> dict:
    episode, turns = validate_episode(episode_dir)
    private = json.loads((Path(episode_dir) / 'result.json').read_text())
    offline = json.loads(Path(offline_receipt).read_text())
    if (offline.get('schema') != 'gui-sft-offline-render-v1' or
            offline.get('model') != MODEL or offline.get('renderer') != RENDERER or
            offline.get('image_processor') != PROCESSOR or
            offline.get('cookbook_commit') != COOKBOOK_COMMIT or
            offline.get('train_task_id') != TRAIN_TASK_ID or
            offline.get('train_template_id') != TRAIN_TEMPLATE_ID or
            offline.get('episode_sha256') != sha(Path(episode_dir) / 'episode.json') or
            offline.get('datum_count') != len(turns) or
            offline.get('paid_provider_calls') != 0 or
            offline.get('optimizer_steps_completed') != 0 or
            offline.get('checkpoint_trained') is not False or
            offline.get('student_improvement_claimed') is not False):
        raise ValueError('offline_receipt_does_not_match_admitted_episode')
    admission = episode['admission']
    derivation = episode.get('derivation')
    if (type(derivation) is not dict or
            derivation.get('kind') != 'action_only_host_memory_removed' or
            derivation.get('executed_actions_and_masked_frames_unchanged') is not True or
            derivation.get('host_memory_used_as_assistant_target') is not False):
        raise ValueError('action_only_derivation_missing')
    if admission.get('native_save_count') != 5 or \
            admission.get('search_index_reset_verified') is not True:
        raise ValueError('five_save_or_search_reset_gate_missing')
    public = {
        'schema': 'magento-gui-sft-train-only-evidence-v1',
        'evidence_class': 'measured_real_gui_development_training_interface',
        'source': {
            'dataset': 'WebArena-Verified',
            'git_commit': private['source']['git_commit'],
            'dataset_sha256': private['source']['dataset_sha256'],
            'task_sha256': private['source']['task_sha256'],
            'evaluator_source_sha256': private['source']['evaluator_source_sha256'],
            'task_id': TRAIN_TASK_ID, 'intent_template_id': TRAIN_TEMPLATE_ID,
        },
        'environment': {
            'application': 'Magento 2.4.6 admin',
            'disposable_image_sha256': private['clone']['image_sha256'],
            'loopback_only': True, 'mounts': 0,
        },
        'gui_recording': {
            'current_masked_pre_action_frames': private['screenshot_count'],
            'validated_normalized_json_actions': private['action_count'],
            'host_only_memory_omitted_from_model_inputs': True,
            'native_gui_saves': admission['native_save_count'],
            'published_evaluator_raw_and_sanitized_score': admission['published_evaluator_score'],
            'raw_and_sanitized_evaluator_equal': admission['raw_and_sanitized_evaluator_equal'],
            'independent_sql_state_pass': private['independent_saved_state_pass'],
            'search_index_state_pass': True,
            'monitored_search_documents': 181,
            'sql_and_search_reset_verified': private['final_reset_verified'],
        },
        'offline_sft': {
            'model': MODEL, 'renderer': RENDERER, 'image_processor': PROCESSOR,
            'cookbook_commit': COOKBOOK_COMMIT,
            'tinker_sdk_version': offline['tinker_sdk_version'],
            'renderer_identity': offline['renderer_identity'],
            'image_plus_action_datums': offline['datum_count'],
            'max_supervised_tokens': offline['max_supervised_tokens'],
            'max_image_tokens': offline['max_image_tokens'],
            'minimum_positive_assistant_loss_weight_sum':
                offline['min_assistant_loss_weight_sum'],
            'paid_tinker_calls': 0, 'optimizer_steps': 0,
            'checkpoint_trained_or_sampled': False,
        },
        'split': train_exclusion_manifest(),
        'action_only_derivation': derivation,
        'private_evidence_sha256': {
            'episode': sha(Path(episode_dir) / 'episode.json'),
            'recorder_result': sha(Path(episode_dir) / 'result.json'),
            'offline_render_receipt': sha(Path(offline_receipt)),
        },
        'publication_boundary': {
            'private_screenshots_or_auth_state_published': False,
            'raw_har_or_model_text_published': False,
            'post_training_task_777_evaluation_permitted_as_held_out': False,
            'trained_improvement_measured': False,
            'official_final_tasks_added': 0,
        },
    }
    if paid_receipt is not None:
        paid = json.loads(Path(paid_receipt).read_text())
        usage = paid.get('measured_rendered_usage') or {}
        preflight = paid.get('paid_preflight') or {}
        if (paid.get('episode_sha256') != offline['episode_sha256'] or
                paid.get('renderer_identity') != offline['renderer_identity'] or
                paid.get('cookbook_commit') != COOKBOOK_COMMIT or
                paid.get('paid_one_step_requested') is not True or
                paid.get('optimizer_steps_completed') != 1 or
                paid.get('checkpoint_saved') is not True or
                paid.get('checkpoint_sampled') is not True or
                paid.get('loss_metrics_available') is not True or
                paid.get('checkpoint_path_published') is not False or
                paid.get('trained_improvement_measured') is not False or
                paid.get('paid_provider_calls') != 2 or
                usage.get('training_input_tokens') != offline['first_supervised_tokens'] or
                usage.get('sampling_prompt_tokens') != offline['first_prompt_tokens'] or
                type(usage.get('sampling_output_tokens')) is not int or
                not 0 <= usage['sampling_output_tokens'] <= 96 or
                usage.get('provider_billed_tokens_known') is not False or
                paid.get('provider_invoice_usd') is not None or
                Decimal(paid['nominal_published_rate_subtotal_usd']) >
                Decimal(preflight['max_published_rate_reservation_usd'])):
            raise ValueError('paid_smoke_receipt_contract_mismatch')
        public['paid_checkpoint_smoke'] = {
            'model': MODEL, 'train_only': True,
            'optimizer_steps_completed': 1,
            'checkpoint_saved_and_sampled': True,
            'loss_metrics_present': True,
            'measured_rendered_training_input_tokens': usage['training_input_tokens'],
            'measured_rendered_sampling_prompt_tokens': usage['sampling_prompt_tokens'],
            'sampled_output_tokens': usage['sampling_output_tokens'],
            'sampled_output_sha256': paid['sample_token_sha256'],
            'published_rate_max_reservation_usd':
                preflight['max_published_rate_reservation_usd'],
            'nominal_published_rate_token_subtotal_usd':
                paid['nominal_published_rate_subtotal_usd'],
            'provider_billed_tokens_known': False,
            'provider_invoice_usd': None,
            'held_out_evaluation_or_improvement_measured': False,
        }
        public['private_evidence_sha256']['paid_smoke_result'] = sha(Path(paid_receipt))
    return public


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode', type=Path, required=True)
    parser.add_argument('--offline-receipt', type=Path, required=True)
    parser.add_argument('--paid-receipt', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    public = public_receipt(args.episode, args.offline_receipt,
                            paid_receipt=args.paid_receipt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(public, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'schema': public['schema'],
                      'datums': public['offline_sft']['image_plus_action_datums'],
                      'official_final_tasks_added': 0}))
