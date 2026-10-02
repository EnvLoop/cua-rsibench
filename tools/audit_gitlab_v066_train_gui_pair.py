"""Independently audit one GitLab v0.6.6 train GUI positive/negative pair.

This reopens every private raw frame, normalized action, provider intent,
saved PostgreSQL/Git state, and fresh-reset artifact. It never runs a model,
Docker, selection/final task, or Tinker optimizer.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import time

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import (
    ContractLimits, Control, Observation,
)
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action
from cursibench.scale_vision_proxy import Limits as VisionLimits, image_from_bytes
from gitlab_world import v066_train_gui_pair as pair
from gitlab_world import train_teacher_oracle_v066 as oracle


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_SCHEMA = 'envloop-gitlab-v066-one-train-gui-pair-audit-private-v1'
PUBLIC_SCHEMA = 'envloop-gitlab-v066-one-train-gui-pair-audit-public-v1'
PRIVATE_OUT = pair.RUN_DIR / 'audit.private.json'
PUBLIC_OUT = ROOT / 'docs/evidence/gitlab-v066-one-train-gui-pair-2026-09-28.json'


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _file(path: Path) -> bytes:
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(pair.RUN_DIR.resolve()) and
            path.stat().st_mode & 0o077 == 0,
            'train_pair_raw_file_missing_or_unsafe')
    return path.read_bytes()


def _json(path: Path) -> tuple[object, str]:
    raw = _file(path)
    return json.loads(raw), pair.sha(raw)


def _observation(trace: dict, image: bytes) -> Observation:
    info = trace['observation']
    _, screenshot = image_from_bytes(image, VisionLimits())
    now = time.monotonic()
    return Observation(
        task_id=info['task_id'],
        task_binding_sha256=info['task_binding_sha256'],
        instruction=info['instruction'],
        step=trace['step'],
        screenshot_bytes=image, screenshot=screenshot,
        a11y_text=info['a11y_text'], dom_text=info['dom_text'],
        controls=tuple(Control.parse(row) for row in info['controls']),
        previous_action_result=info['previous_action_result'],
        memory=info['memory'], frame_id=trace['frame_id'],
        issued_at=now, expires_at=now + 270,
        limits=ContractLimits(),
    )


def _trace(arm: str, task: dict, refs: list[dict],
           trace_path: Path) -> tuple[list[dict], list[dict], str]:
    directory = pair.RUN_DIR / arm
    trace, trace_sha = _json(trace_path)
    require(type(trace) is list and len(trace) == len(refs) and
            1 < len(trace) <= pair.MAX_ACTIONS_PER_ARM,
            'train_gui_action_trace_length_changed')
    turns = []
    usage = []
    for index, (row, reference) in enumerate(zip(trace, refs, strict=True)):
        require(type(row) is dict and row.get('step') == index and
                type(reference) is dict and
                reference.get('path') == f'frames/step-{index:03d}.png',
                'train_gui_frame_order_changed')
        image = _file(directory / reference['path'])
        require(pair.sha(image) == reference.get('sha256') ==
                row.get('frame_sha256'),
                'train_gui_raw_frame_changed')
        observation = _observation(row, image)
        require(observation.task_id == task['task_id'] and
                observation.task_binding_sha256 == task['package_sha256'] and
                observation.instruction == task['visible_instruction'] and
                row.get('frame_id') == observation.frame_id and
                row.get('observation', {}).get('issued_at') is not None and
                validate_action(row['action'], observation,
                                current_frame_id=observation.frame_id) ==
                row['action'],
                'train_gui_normalized_v066_action_invalid')
        provider_root = pair.RUN_DIR / (arm + '-provider')
        intent, _ = _json(provider_root /
                          f'step-{index:03d}-intent.private.json')
        request, request_sha = _json(provider_root /
                                     f'step-{index:03d}-request.private.json')
        response, response_sha = _json(provider_root /
                                        f'step-{index:03d}-response.private.json')
        require(intent.get('arm') == arm and intent.get('step') == index and
                intent.get('frame_id') == observation.frame_id and
                intent.get('frame_sha256') == reference['sha256'] and
                intent.get('request_sha256') == request_sha and
                intent.get('provider_replay_authorized') is False and
                request.get('model') == teacher.matrix.TEACHER and
                request.get('image_data_url', '').startswith(
                    'data:image/png;base64,') and
                base64.b64decode(request['image_data_url'].split(',', 1)[1]) == image and
                json.loads(request['user_text']).get('task_instruction') ==
                task['visible_instruction'] and
                json.loads(request['user_text']).get('arm') == arm and
                normalize_model_action(
                    response['text'], observation,
                    current_frame_id=observation.frame_id) == row['action'] and
                response_sha == row.get('teacher_result_sha256') and
                response.get('receipt', {}).get('reported_model') ==
                teacher.matrix.TEACHER and
                response['receipt'].get('status') == 'completed' and
                type(response['receipt'].get('usage')) is dict,
                'train_gui_provider_intent_response_or_frame_changed')
        usage.append(response['receipt']['usage'])
        turns.append({'observation': observation,
                      'action': row['action'],
                      'trace_row': row,
                      'teacher_result_sha256': response_sha})
    require(turns[-1]['action']['type'] == 'finish' and
            all(turn['action']['type'] != 'finish' for turn in turns[:-1]),
            'train_gui_finish_missing_or_premature')
    return turns, usage, trace_sha


def _positive(task: dict, original: dict, plan: dict,
              expected_sha: str) -> dict:
    directory = pair.RUN_DIR / 'positive'
    episode, episode_sha = _json(directory / 'episode.private.json')
    require(type(episode) is dict and episode_sha == expected_sha and
            episode.get('schema') == teacher.EPISODE_SCHEMA and
            episode.get('status') == 'admitted' and
            episode.get('split') == 'train' and
            episode.get('task_id') == task['task_id'] and
            episode.get('package_sha256') == task['package_sha256'] and
            episode.get('action_profile') ==
            pair.worker.ACTION_PROFILE_VERSION and
            episode.get('runtime_sha256') == plan['worker_runtime_sha256'] and
            episode.get('adapter_sha256') == pair.worker.adapter_sha256() and
            episode.get('e2b_attempt_ids') == [],
            'positive_teacher_episode_not_bound_to_train_source')
    trace_ref = episode['action_trace_ref']
    require(trace_ref.get('path') == 'actions.private.json',
            'positive_teacher_trace_path_changed')
    turns, usage, trace_sha = _trace(
        'positive', task, episode['frame_refs'], directory / trace_ref['path'])
    require(trace_sha == trace_ref.get('sha256'),
            'positive_teacher_trace_hash_changed')
    teacher._verify_episode(
        directory,
        {'episode_receipt_path': str(directory / 'episode.private.json'),
         'episode_receipt_sha256': episode_sha},
        cell_id='gitlab', task=task,
        runtime_sha=plan['worker_runtime_sha256'],
        adapter_sha=pair.worker.adapter_sha256(),
        verifier_sha=plan['worker_verifier_sha256'],
        turns=turns, e2b_attempt_ids=[], requires_e2b=False)
    saved = teacher._json_ref(directory, episode['saved_state_ref'])
    artifact = teacher._json_ref(directory, saved['saved_artifact_ref'])
    baseline = teacher._json_ref(directory,
                                 teacher._json_ref(directory, episode['reset_ref'])[
                                     'baseline_state_ref'])
    reset = teacher._json_ref(directory, episode['reset_ref'])
    restored = teacher._json_ref(directory, reset['restored_state_ref'])
    before = baseline['business_snapshot']
    after = artifact['business_snapshot']
    score = oracle.evaluate_train_task(original, before, after)
    require(score['reward'] == 1.0 and score['checks_passed'] is True and
            score['difference_codes'] == [] and
            artifact['independent_score'] == score and
            baseline == restored and
            reset['state_equivalence_pass'] is True and
            reset['sandbox_terminated'] is True,
            'positive_saved_postgresql_git_or_exact_reset_changed')
    return {'episode_sha256': episode_sha, 'trace_sha256': trace_sha,
            'actions': len(turns), 'baseline': before,
            'saved_business_sha256': after['business_sha256'],
            'provider_usage': usage}


def _negative(task: dict, original: dict, baseline: dict,
              expected_sha: str) -> dict:
    directory = pair.RUN_DIR / 'negative'
    episode, episode_sha = _json(directory / 'negative-episode.private.json')
    require(type(episode) is dict and episode_sha == expected_sha and
            episode.get('schema') == pair.NEGATIVE_SCHEMA and
            episode.get('status') == 'plausible_negative_rejected' and
            episode.get('split') == 'train' and
            episode.get('task_id') == task['task_id'] and
            episode.get('package_sha256') == task['package_sha256'] and
            episode.get('action_profile') ==
            pair.worker.ACTION_PROFILE_VERSION and
            episode.get('wrong_priority_only') is True and
            episode.get('independent_reward') == 0.0 and
            episode.get('fresh_cold_reset_exact') is True and
            episode.get('official_final_admitted') == 0,
            'negative_arm_identity_or_wrong_variant_changed')
    turns, usage, trace_sha = _trace(
        'negative', task, episode['frame_refs'],
        directory / 'actions.private.json')
    saved, saved_sha = _json(directory / 'saved.private.json')
    baseline_state, baseline_sha = _json(directory / 'baseline.private.json')
    restored_state, restored_sha = _json(directory / 'restored.private.json')
    require(trace_sha == episode['action_trace_sha256'] and
            saved_sha == episode['saved_state_sha256'] and
            baseline_sha == episode['baseline_sha256'] and
            restored_sha == episode['restored_sha256'] and
            episode['provider_result_sha256s'] ==
            [turn['teacher_result_sha256'] for turn in turns] and
            baseline_state == restored_state and
            baseline_state['business_snapshot'] == baseline and
            saved['independent_score']['reward'] == 0.0 and
            oracle.evaluate_train_task(
                original, baseline, saved['business_snapshot'])['reward'] == 0.0 and
            pair._negative_plausible(
                original, baseline, saved['business_snapshot']),
            'negative_plausible_saved_state_or_cold_reset_changed')
    return {'episode_sha256': episode_sha, 'trace_sha256': trace_sha,
            'actions': len(turns), 'provider_usage': usage,
            'saved_business_sha256':
            saved['business_snapshot']['business_sha256']}


def audit(ratification_path: Path) -> tuple[dict, dict]:
    plan, original, task, plan_sha = pair.validate_plan(ratification_path)
    run, run_sha = _json(pair.RUN_DIR / 'run.private.json')
    require(type(run) is dict and run.get('schema') == pair.RUN_SCHEMA and
            run.get('status') ==
            'two_train_gui_arms_recorded_pending_independent_audit' and
            run.get('plan_sha256') == plan_sha and
            run.get('official_final_admitted') == 0 and
            run.get('tinker_sft_eligible') is False and
            not (pair.RUN_DIR / 'failure.private.json').exists(),
            'train_pair_not_complete_for_independent_audit')
    positive = _positive(task, original, plan, run['positive_episode_sha256'])
    negative = _negative(task, original, positive['baseline'],
                         run['negative_episode_sha256'])
    require(run.get('positive_action_count') == positive['actions'] and
            run.get('negative_action_count') == negative['actions'] and
            run.get('provider_usage') ==
            positive['provider_usage'] + negative['provider_usage'] and
            positive['saved_business_sha256'] !=
            negative['saved_business_sha256'],
            'train_pair_actions_usage_or_positive_negative_state_changed')
    private = {'schema': PRIVATE_SCHEMA,
               'status': 'one_real_original_gitlab_train_gui_pair_independently_validated',
               'task_id': task['task_id'],
               'package_sha256': task['package_sha256'],
               'plan_sha256': plan_sha, 'run_sha256': run_sha,
               'source_bundle_sha256': plan['source_bundle_sha256'],
               'positive_episode_sha256': positive['episode_sha256'],
               'negative_episode_sha256': negative['episode_sha256'],
               'positive_actions': positive['actions'],
               'negative_actions': negative['actions'],
               'provider_usage': run['provider_usage'],
               'non_admin_train_acl_bound': True,
               'selection_final_content_exposed_to_actor': False,
               'positive_eligible_for_tinker_gui_sft': True,
               'negative_is_verifier_control_only': True,
               'official_final_admitted': 0}
    public = {'schema': PUBLIC_SCHEMA,
              'status': 'one_train_gui_pair_passed_sft_eligibility_not_final_admission',
              'cell_id': 'gitlab', 'original_software': 'GitLab CE 18.5',
              'action_profile': pair.worker.ACTION_PROFILE_VERSION,
              'plan_sha256': plan_sha,
              'source_bundle_sha256': plan['source_bundle_sha256'],
              'positive_episode_sha256': positive['episode_sha256'],
              'negative_episode_sha256': negative['episode_sha256'],
              'positive_actions': positive['actions'],
              'negative_actions': negative['actions'],
              'raw_current_frames_reopened':
              positive['actions'] + negative['actions'],
              'independent_saved_positive_reward': 1.0,
              'plausible_wrong_priority_reward': 0.0,
              'exact_cold_resets': 2,
              'non_admin_train_acl_bound': True,
              'selection_final_content_exposed_to_actor': False,
              'positive_eligible_for_tinker_gui_sft': True,
              'tinker_optimizer_steps': 0,
              'official_final_admitted': 0,
              'researcher_campaigns': 0}
    return private, public


def _write_new(path: Path, value: dict, mode: int) -> str:
    require(not path.exists() and not path.is_symlink(),
            'fresh_train_pair_audit_output_required')
    raw = pair.canonical(value)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return pair.sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ratification-private', type=Path, required=True)
    args = parser.parse_args()
    private, public = audit(args.ratification_private)
    private_sha = _write_new(PRIVATE_OUT, private, 0o600)
    public['private_audit_sha256'] = private_sha
    _write_new(PUBLIC_OUT, public, 0o644)
    print(json.dumps({
        'status': public['status'],
        'positive_eligible_for_tinker_gui_sft': True,
        'official_final_admitted': 0,
        'tinker_optimizer_steps': 0,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
