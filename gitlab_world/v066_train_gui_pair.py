"""One source-bound original-GitLab v0.6.6 train GUI positive/negative pair.

The positive arm uses the existing Tinker-compatible teacher episode worker.
The negative arm uses the same current-frame GUI backend and independent
PostgreSQL/Git oracle. Neither arm can access selection/final task content.
No provider, Docker, or model call happens during the offline freeze.
"""

from __future__ import annotations

import argparse
import base64
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
from typing import Callable

from cursibench import full_study_teacher_adapter_v1 as teacher
from cursibench.scale_action_contract import Observation
from cursibench.scale_action_contract_v066 import validate_action
from cursibench.scale_action_output_v066 import normalize_model_action, render_for_model
from native_desktop_factory.v066_final_freeze import validate_ratification

from . import (bootstrap, factory, runtime, teacher_episode_worker_v066 as worker,
               train_teacher_oracle_v066 as oracle, verify)


ROOT = Path(__file__).resolve().parents[1]
PLAN_SCHEMA = 'envloop-gitlab-v066-one-train-gui-pair-plan-private-v1'
PUBLIC_PLAN_SCHEMA = 'envloop-gitlab-v066-one-train-gui-pair-plan-public-v1'
NEGATIVE_SCHEMA = 'envloop-gitlab-v066-train-wrong-priority-gui-arm-v1'
RUN_SCHEMA = 'envloop-gitlab-v066-one-train-gui-pair-run-private-v1'
PLAN = runtime.PRIVATE / 'v066-one-train-gui-pair-plan.private.json'
PUBLIC_PLAN = ROOT / 'docs/evidence/gitlab-v066-one-train-gui-pair-plan-2026-09-28.json'
RUN_DIR = runtime.PRIVATE / 'v066-one-train-gui-pair-20260928'
MAX_ACTIONS_PER_ARM = 45
WALL_SECONDS_PER_ARM = 1200
SOURCE_FILES = (
    'gitlab_world/v066_train_gui_pair.py',
    'tools/audit_gitlab_v066_train_gui_pair.py',
    'gitlab_world/teacher_episode_worker_v066.py',
    'gitlab_world/vision_actor_v066_train.py',
    'gitlab_world/train_teacher_oracle_v066.py',
    'gitlab_world/verify.py', 'gitlab_world/reset.py',
    'gitlab_world/runtime.py', 'gitlab_world/operators.py',
    'gitlab_world/bootstrap.py', 'gitlab_world/factory.py',
    'src/cursibench/full_study_teacher_adapter_v1.py',
    'src/cursibench/scale_action_contract_v066.py',
    'src/cursibench/scale_action_output_v066.py',
)
_HEX = re.compile(r'[0-9a-f]{64}\Z')


class PairError(RuntimeError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PairError(code)


def sha(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def canonical(value: object) -> bytes:
    return teacher._canonical(value)


def source_sha256s() -> dict[str, str]:
    return {relative: sha((ROOT / relative).read_bytes())
            for relative in SOURCE_FILES}


def write_new(path: Path, value: object) -> str:
    raw = canonical(value)
    require(path.parent.is_dir() and not path.parent.is_symlink() and
            path.parent.stat().st_mode & 0o077 == 0 and
            not path.exists() and not path.is_symlink(),
            'private_train_pair_output_not_fresh_or_restrictive')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def _private_json(path: Path, *, legacy_enclosed: bool = False) -> tuple[dict, str]:
    require(path.is_file() and not path.is_symlink() and
            (path.stat().st_mode & 0o077 == 0 or
             (legacy_enclosed and runtime.PRIVATE.is_dir() and
              runtime.PRIVATE.stat().st_mode & 0o077 == 0)) and
            path.resolve().is_relative_to(runtime.PRIVATE.resolve()),
            'private_train_pair_evidence_missing_or_unsafe')
    raw = path.read_bytes()
    value = json.loads(raw)
    require(type(value) is dict, 'private_train_pair_json_object_required')
    return value, sha(raw)


def _train_task() -> tuple[dict, dict]:
    require(bootstrap.WORLD_FILE.is_file() and
            bootstrap.WORLD_FILE.stat().st_mode & 0o077 == 0,
            'original_private_gitlab_world_required')
    world = json.loads(bootstrap.WORLD_FILE.read_bytes())
    require(world.get('schema') == factory.SCHEMA and
            world.get('source', {}).get('excerpt_sha256') == factory.EXCERPT_SHA256,
            'pinned_cisa_anchored_gitlab_world_changed')
    train = [row for row in world['tasks'] if row['partition'] == 'train']
    matches = sorted((row for row in train
                      if row['template_group'] == 'issue_label_from_alert'),
                     key=lambda row: row['task_id'])
    require(len(train) == 20 and len(matches) == 5 and
            not any(row['partition'] != 'train' for row in matches),
            'one_label_task_must_come_from_train_partition')
    task = matches[0]
    binding = {'task_id': task['task_id'],
               'package_sha256': factory.sha256(factory.canonical(task)),
               'visible_instruction': task['prompt']}
    return task, binding


def _acl_and_split_evidence() -> dict:
    acl_path = runtime.PRIVATE / 'operator-acl-gui-summary.json'
    split_path = runtime.PRIVATE / 'gui-sft-splits-private/public-fields.json'
    acl, acl_sha = _private_json(acl_path, legacy_enclosed=True)
    split, split_sha = _private_json(split_path, legacy_enclosed=True)
    require(acl.get('acl_gui_passed') is True and
            acl.get('own_project_gui_successes') == 3 and
            acl.get('cross_partition_gui_denials') == 6 and
            acl.get('root_admin_actor_used') is False and
            split.get('selection_count') == 20 and
            split.get('clean_final_candidate_count') == 100 and
            split.get('train_source_disjoint_from_selection_and_final') is True and
            split.get('accepted_training_episodes') == 0 and
            split.get('official_final_admitted') == 0,
            'train_operator_acl_or_split_boundary_not_proven')
    return {'acl_receipt_sha256': acl_sha,
            'split_receipt_sha256': split_sha,
            'train_operator_non_admin': True,
            'cross_partition_gui_denials': 6}


def freeze(ratification_path: Path) -> dict:
    require(not PLAN.exists() and not PUBLIC_PLAN.exists() and
            runtime.PRIVATE.is_dir() and
            runtime.PRIVATE.stat().st_mode & 0o077 == 0 and
            ratification_path.is_file() and
            not ratification_path.is_symlink() and
            ratification_path.stat().st_mode & 0o077 == 0,
            'fresh_private_train_pair_freeze_and_ratification_required')
    ratification, rat_sha = validate_ratification(ratification_path)
    require(ratification['cell_profiles']['gitlab']['adapter_sha256'] ==
            worker.adapter_sha256() and
            ratification['action_profile'] == worker.ACTION_PROFILE_VERSION,
            'gitlab_v066_adapter_differs_from_six_cell_ratification')
    original, binding = _train_task()
    boundary = _acl_and_split_evidence()
    source = source_sha256s()
    baseline_path = runtime.PRIVATE / 'baseline-persisted-state.json'
    require(baseline_path.is_file() and
            baseline_path.stat().st_mode & 0o077 == 0,
            'gitlab_baseline_evidence_missing')
    value = {'schema': PLAN_SCHEMA,
             'status': 'train_only_pre_result_no_episode_yet',
             'cell_id': 'gitlab', 'partition': 'train',
             'train_task_id': binding['task_id'],
             'train_package_sha256': binding['package_sha256'],
             'visible_instruction_sha256': sha(binding['visible_instruction'].encode()),
             'original_task_sha256': factory.sha256(factory.canonical(original)),
             'world_sha256': sha(bootstrap.WORLD_FILE.read_bytes()),
             'baseline_sha256': sha(baseline_path.read_bytes()),
             'ratification_sha256': rat_sha,
             'source_sha256s': source,
             'source_bundle_sha256': sha(canonical(source)),
             'worker_runtime_sha256': worker.runtime_sha256(),
             'worker_verifier_sha256': worker.verifier_sha256(),
             'acl_and_split': boundary,
             'teacher_model': teacher.matrix.TEACHER,
             'max_actions_per_arm': MAX_ACTIONS_PER_ARM,
             'one_positive_and_one_wrong_priority_negative': True,
             'provider_replay_authorized': False,
             'selection_final_task_content_exposed_to_actor': False,
             'model_calls': 0, 'official_final_admitted': 0}
    plan_sha = write_new(PLAN, value)
    public = {'schema': PUBLIC_PLAN_SCHEMA,
              'status': 'source_frozen_one_train_task_no_gui_episode_or_final_admission',
              'cell_id': 'gitlab', 'partition': 'train',
              'private_plan_sha256': plan_sha,
              'source_bundle_sha256': value['source_bundle_sha256'],
              'ratification_sha256': rat_sha,
              'acl_receipt_sha256': boundary['acl_receipt_sha256'],
              'split_receipt_sha256': boundary['split_receipt_sha256'],
              'positive_arms_recorded': 0, 'negative_arms_recorded': 0,
              'tinker_sft_eligible_episodes': 0,
              'official_final_admitted': 0, 'model_calls': 0}
    raw = canonical(public)
    descriptor = os.open(PUBLIC_PLAN, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return public


def validate_plan(ratification_path: Path) -> tuple[dict, dict, dict, str]:
    plan, plan_sha = _private_json(PLAN)
    public = json.loads(PUBLIC_PLAN.read_bytes())
    original, binding = _train_task()
    boundary = _acl_and_split_evidence()
    ratification, rat_sha = validate_ratification(ratification_path)
    require(plan.get('schema') == PLAN_SCHEMA and
            plan.get('status') == 'train_only_pre_result_no_episode_yet' and
            plan.get('partition') == 'train' and
            plan.get('train_task_id') == binding['task_id'] and
            plan.get('train_package_sha256') == binding['package_sha256'] and
            plan.get('visible_instruction_sha256') ==
            sha(binding['visible_instruction'].encode()) and
            plan.get('world_sha256') == sha(bootstrap.WORLD_FILE.read_bytes()) and
            plan.get('baseline_sha256') ==
            sha((runtime.PRIVATE / 'baseline-persisted-state.json').read_bytes()) and
            plan.get('ratification_sha256') == rat_sha and
            ratification['cell_profiles']['gitlab']['adapter_sha256'] ==
            worker.adapter_sha256() and
            plan.get('source_sha256s') == source_sha256s() and
            plan.get('source_bundle_sha256') == sha(canonical(source_sha256s())) and
            plan.get('worker_runtime_sha256') == worker.runtime_sha256() and
            plan.get('worker_verifier_sha256') == worker.verifier_sha256() and
            plan.get('acl_and_split') == boundary and
            plan.get('provider_replay_authorized') is False and
            plan.get('selection_final_task_content_exposed_to_actor') is False and
            plan.get('model_calls') == plan.get('official_final_admitted') == 0 and
            public.get('schema') == PUBLIC_PLAN_SCHEMA and
            public.get('private_plan_sha256') == plan_sha and
            public.get('source_bundle_sha256') == plan['source_bundle_sha256'] and
            public.get('positive_arms_recorded') ==
            public.get('negative_arms_recorded') ==
            public.get('tinker_sft_eligible_episodes') == 0,
            'source_bound_one_train_gui_plan_changed')
    return plan, original, binding, plan_sha


def _trace_row(observation: Observation, action: dict,
               response_sha256: str) -> dict:
    return {'step': observation.step, 'frame_id': observation.frame_id,
            'frame_sha256': sha(observation.screenshot_bytes),
            'observation': {
                'task_id': observation.task_id,
                'task_binding_sha256': observation.task_binding_sha256,
                'instruction': observation.instruction,
                'a11y_text': observation.a11y_text,
                'dom_text': observation.dom_text,
                'controls': [vars(control) for control in observation.controls],
                'previous_action_result': observation.previous_action_result,
                'memory': observation.memory,
                'issued_at': observation.issued_at,
            }, 'action': action, 'teacher_result_sha256': response_sha256}


class SolSampler:
    """One bounded Responses image call per current original-GUI frame."""

    def __init__(self, *, arm: str, provider: Callable | None = None):
        require(arm in ('positive', 'negative'), 'unknown_train_arm')
        self.arm = arm
        self.provider = provider or teacher._real_teacher_provider
        self.turns: list[dict] = []
        self.provider_usage: list[dict] = []
        self.directory = RUN_DIR / (arm + '-provider')

    def sample(self, observation: Observation,
               current_frame_id: Callable[[], str]) -> dict:
        step = len(self.turns)
        require(step == observation.step and step < MAX_ACTIONS_PER_ARM and
                current_frame_id() == observation.frame_id,
                'current_train_frame_or_action_budget_changed')
        rendered = render_for_model(observation)
        request = {
            'model': teacher.matrix.TEACHER,
            'reasoning_effort': 'medium', 'reasoning_mode': 'standard',
            'max_output_tokens': 1024,
            'image_detail': 'high',
            'image_data_url': 'data:image/png;base64,' +
                              base64.b64encode(observation.screenshot_bytes).decode(),
            'system_prompt': (
                'Operate only the visible original GitLab UI. Return exactly one '
                'v0.6.6 JSON GUI action per reply. No URLs, APIs, selectors, shell, '
                'or file operations. Finish only after a visible save. ' +
                ('Complete the user training instruction exactly.'
                 if self.arm == 'positive' else
                 'For verifier calibration, make exactly one plausible wrong '
                 'priority-label choice on the active issue. Preserve every '
                 'other issue, project, member and Git record.')),
            'user_text': canonical({
                'task_instruction': observation.instruction,
                'model_instruction': rendered['instruction'],
                'visible_text': rendered['visible_text'],
                'arm': self.arm,
            }).decode(),
        }
        intent = {'schema': 'envloop-gitlab-v066-train-sol-call-intent-v1',
                  'arm': self.arm, 'step': step,
                  'frame_sha256': sha(observation.screenshot_bytes),
                  'frame_id': observation.frame_id,
                  'request_sha256': sha(canonical(request)),
                  'provider_replay_authorized': False}
        write_new(self.directory / f'step-{step:03d}-request.private.json', request)
        write_new(self.directory / f'step-{step:03d}-intent.private.json', intent)
        response = self.provider(request, 180)
        require(type(response) is dict and set(response) == {'text', 'receipt'} and
                type(response['text']) is str and
                type(response['receipt']) is dict and
                response['receipt'].get('reported_model') == teacher.matrix.TEACHER and
                response['receipt'].get('status') == 'completed' and
                type(response['receipt'].get('response_id')) is str and
                bool(response['receipt']['response_id']) and
                type(response['receipt'].get('usage')) is dict,
                'sol_teacher_response_or_usage_ambiguous_no_retry')
        response_sha = write_new(
            self.directory / f'step-{step:03d}-response.private.json', response)
        require(current_frame_id() == observation.frame_id,
                'paid_teacher_frame_changed_no_replay')
        action = normalize_model_action(
            response['text'], observation,
            current_frame_id=current_frame_id())
        validate_action(action, observation,
                        current_frame_id=current_frame_id())
        trace = _trace_row(observation, action, response_sha)
        turn = {'observation': observation, 'action': action,
                'trace_row': trace,
                'teacher_result_sha256': response_sha}
        self.turns.append(turn)
        self.provider_usage.append(response['receipt']['usage'])
        return {'action': action, 'trace_row': trace,
                'teacher_result_sha256': response_sha}


def _negative_plausible(original: dict, before: dict, after: dict) -> bool:
    if (original['partition'] != 'train' or
            original['template_group'] != 'issue_label_from_alert' or
            oracle.evaluate_train_task(original, before, after)['reward'] != 0.0 or
            before['business_sha256'] == after['business_sha256']):
        return False
    try:
        project, progress = verify._context(original)
        project_id = int(progress['project_id'])
        active = verify._issue(before, project_id,
                               int(progress['issue_iids']['active']))
        verify._unchanged_tables(before, after, 'issue_label_links')
        verify._unchanged_other_git(before, after, project_id)
        old = verify._rows_by_id(before['db']['issue_label_links'])
        new = verify._rows_by_id(after['db']['issue_label_links'])
        added = set(new) - set(old)
        if len(added) != 1 or set(old) - set(new) or any(new[k] != old[k] for k in old):
            return False
        link = new[next(iter(added))]
        correct = verify._project_label_id(
            before, project_id, original['oracle']['expected_priority'])
        labels = {row['id']: row for row in before['db']['labels']
                  if row['project_id'] == project_id}
        return (link['target_id'] == active['id'] and
                link['label_id'] != correct and
                link['label_id'] in labels and
                labels[link['label_id']]['title'] in
                {'priority::p1', 'priority::p2'})
    except (KeyError, ValueError, verify.QualificationError):
        return False


def _negative_arm(task: dict, original: dict, sampler: SolSampler) -> dict:
    arm = RUN_DIR / 'negative'
    arm.mkdir(mode=0o700)
    frames = arm / 'frames'
    frames.mkdir(mode=0o700)
    sampler.directory.mkdir(mode=0o700)
    backend = worker.RealGitLabTrainBackend()
    refs = []
    memory = ''
    session = None
    saved = None
    start = time.monotonic()
    with backend.open(task) as active:
        session = active
        require(active.pre_restore_exact is True,
                'negative_train_baseline_not_exact')
        for step in range(MAX_ACTIONS_PER_ARM):
            require(time.monotonic() - start < WALL_SECONDS_PER_ARM,
                    'negative_train_wall_budget_exhausted')
            observation = active.observe(memory=memory)
            require(observation.step == step and
                    observation.task_id == task['task_id'] and
                    observation.task_binding_sha256 == task['package_sha256'],
                    'negative_train_observation_binding_changed')
            frame_path = frames / f'step-{step:03d}.png'
            descriptor = os.open(frame_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(observation.screenshot_bytes)
                stream.flush()
                os.fsync(stream.fileno())
            refs.append({'path': 'frames/' + frame_path.name,
                         'sha256': sha(observation.screenshot_bytes)})
            sampled = sampler.sample(observation, active.current_frame_id)
            active.dispatch(sampled['action'])
            memory = sampled['action']['memory']
            if sampled['action']['type'] == 'finish':
                saved = active.read_saved_state()
                break
        else:
            raise PairError('negative_train_action_budget_exhausted')
    require(session is not None and session.post_restore_exact is True and
            session.environment_terminated is True and
            session.reset_semantic == session.baseline_semantic and
            saved is not None and
            saved['independent_score']['reward'] == 0.0 and
            _negative_plausible(original,
                                session.baseline_semantic['business_snapshot'],
                                saved['business_snapshot']),
            'negative_wrong_priority_or_exact_cold_reset_not_verified')
    trace = [turn['trace_row'] for turn in sampler.turns]
    trace_sha = write_new(arm / 'actions.private.json', trace)
    saved_sha = write_new(arm / 'saved.private.json', saved)
    baseline_sha = write_new(arm / 'baseline.private.json', session.baseline_semantic)
    restored_sha = write_new(arm / 'restored.private.json', session.reset_semantic)
    receipt = {'schema': NEGATIVE_SCHEMA, 'status': 'plausible_negative_rejected',
               'cell_id': 'gitlab', 'split': 'train',
               'task_id': task['task_id'],
               'package_sha256': task['package_sha256'],
               'action_profile': worker.ACTION_PROFILE_VERSION,
               'frame_refs': refs,
               'action_trace_sha256': trace_sha,
               'saved_state_sha256': saved_sha,
               'baseline_sha256': baseline_sha,
               'restored_sha256': restored_sha,
               'wrong_priority_only': True,
               'independent_reward': 0.0,
               'fresh_cold_reset_exact': True,
               'provider_result_sha256s': [turn['teacher_result_sha256']
                                           for turn in sampler.turns],
               'official_final_admitted': 0}
    digest = write_new(arm / 'negative-episode.private.json', receipt)
    return {'receipt_sha256': digest, 'receipt': receipt}


def record(ratification_path: Path,
           *, provider: Callable | None = None) -> dict:
    plan, original, task, plan_sha = validate_plan(ratification_path)
    require(not RUN_DIR.exists() and bool(os.environ.get('OPENAI_API_KEY') or provider),
            'fresh_train_pair_run_and_teacher_route_required')
    RUN_DIR.mkdir(mode=0o700)
    positive = RUN_DIR / 'positive'
    positive.mkdir(mode=0o700)
    (positive / 'frames').mkdir(mode=0o700)
    pos_sampler = SolSampler(arm='positive', provider=provider)
    pos_sampler.directory.mkdir(mode=0o700)
    worker_instance = worker.GitLabTrainEpisodeWorker(
        private_output_root=RUN_DIR,
        ratification_path=ratification_path,
        ratification_sha256=plan['ratification_sha256'],
        expected_runtime_sha256=plan['worker_runtime_sha256'],
        expected_verifier_sha256=plan['worker_verifier_sha256'],
        enable_live=True)
    write_new(RUN_DIR / 'positive-intent.private.json', {
        'schema': 'envloop-gitlab-v066-train-arm-intent-v1',
        'arm': 'positive', 'task_id': task['task_id'],
        'plan_sha256': plan_sha, 'provider_replay_authorized': False})
    try:
        result = worker_instance.run_episode(
            task=task, out_dir=positive,
            sample_teacher=pos_sampler.sample,
            dispatch_e2b=lambda **_kwargs: (_ for _ in ()).throw(
                PairError('self_hosted_gitlab_has_no_e2b_lease')))
        teacher._verify_episode(
            positive, result, cell_id='gitlab', task=task,
            runtime_sha=plan['worker_runtime_sha256'],
            adapter_sha=worker.adapter_sha256(),
            verifier_sha=plan['worker_verifier_sha256'],
            turns=pos_sampler.turns, e2b_attempt_ids=[], requires_e2b=False)
        write_new(RUN_DIR / 'negative-intent.private.json', {
            'schema': 'envloop-gitlab-v066-train-arm-intent-v1',
            'arm': 'negative', 'task_id': task['task_id'],
            'plan_sha256': plan_sha, 'provider_replay_authorized': False})
        neg_sampler = SolSampler(arm='negative', provider=provider)
        negative = _negative_arm(task, original, neg_sampler)
        receipt = {'schema': RUN_SCHEMA,
                   'status': 'two_train_gui_arms_recorded_pending_independent_audit',
                   'plan_sha256': plan_sha,
                   'positive_episode_sha256': result['episode_receipt_sha256'],
                   'negative_episode_sha256': negative['receipt_sha256'],
                   'positive_action_count': len(pos_sampler.turns),
                   'negative_action_count': len(neg_sampler.turns),
                   'teacher_model': teacher.matrix.TEACHER,
                   'provider_usage': pos_sampler.provider_usage +
                                     neg_sampler.provider_usage,
                   'official_final_admitted': 0,
                   'tinker_sft_eligible': False}
        run_sha = write_new(RUN_DIR / 'run.private.json', receipt)
        return {'status': receipt['status'],
                'private_run_sha256': run_sha,
                'positive_action_count': receipt['positive_action_count'],
                'negative_action_count': receipt['negative_action_count'],
                'tinker_sft_eligible': False,
                'official_final_admitted': 0}
    except BaseException as exc:
        if not (RUN_DIR / 'failure.private.json').exists():
            write_new(RUN_DIR / 'failure.private.json', {
                'schema': 'envloop-gitlab-v066-train-pair-failure-v1',
                'reason_type': type(exc).__name__,
                'positive_teacher_calls': len(pos_sampler.turns),
                'provider_replay_authorized': False,
                'official_final_admitted': 0})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('freeze', 'record'))
    parser.add_argument('--ratification-private', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.action == 'freeze':
        result = freeze(args.ratification_private)
    else:
        require(args.execute, 'explicit_train_gui_pair_execute_required')
        result = record(args.ratification_private)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
