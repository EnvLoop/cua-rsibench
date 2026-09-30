"""Read-only terminal audit of the consumed prospective v5 GitLab prefix.

No Docker, application, provider, fresh permit, or unconsumed task is accessed.
This reports saved positive semantics separately from incomplete reset/trios.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from io import BytesIO
from PIL import Image
from . import factory, gui_controls, verify
from . import v066_prospective_cohort_v5 as source
from . import v066_prospective_cohort_controller_v5 as controller
from . import v066_prospective_cohort_runtime_v5 as scoped


def require(ok, message):
    if not ok:
        raise ValueError(message)


def classify_boot(state: dict, stdout: bytes, stderr: bytes) -> dict:
    combined = stdout + b'\n' + stderr
    recognized = all(token in combined for token in (
        b'gitlab-ctl reconfigure', b'runit_service[postgresql]',
        b'restart_log_service', b'/opt/gitlab/embedded/bin/sv restart /opt/gitlab/service/postgresql/log',
        b'timeout: down: /opt/gitlab/service/postgresql/log'))
    require(state.get('Status') == 'exited' and state.get('Running') is False and
            state.get('ExitCode') == 1 and state.get('OOMKilled') is False and recognized,
            'Saved terminal failure is not the recognized non-OOM log-service restart timeout')
    return {'observed_failure': 'postgresql_log_service_restart_timeout_during_reconfigure',
            'container_exit_code': 1, 'container_oom_killed': False,
            'low_level_logger_restart_cause': None,
            'uniform_svwait_60_empirically_validated': False}


def audit(*, freeze: Path, detached: Path, out: Path, public_out: Path) -> dict:
    require(not out.exists() and not public_out.exists(), 'New exclusive review outputs required')
    value = source.validate_source(freeze)
    prefix = controller.audit_prefix(freeze_path=freeze)
    require(prefix.get('new_baseline_controls_completed') == 3 and
            prefix.get('terminal_failure') is True and prefix.get('pending_intent') is False,
            'Actual consumed v5 prefix differs from three passes then terminal failure')
    root = Path(value['epoch_root'])
    plan, plan_sha, baseline = controller.baseline_inputs(value, freeze)
    rows = controller.read_journal(root)
    state = controller.journal_state(rows)
    require([row['task_index'] for row in state['completed']] == [0, 1, 2] and
            len(rows) == 8 and rows[-1]['kind'] == 'terminal' and
            rows[-1]['task_index'] == 3 and rows[-1]['passed'] is False,
            'No exact index-three consumed terminal record')
    folder = root / 'controls/supervision'
    raw = source.private(folder / '003-result.private.json'); result = json.loads(raw)
    child = result['child']
    require(source.sha(raw) == rows[-1]['supervisor_result_sha256'] and
            child.get('exit_code') == 1 and child.get('timed_out') is False and
            child.get('process_group_terminated') is True and
            child.get('termination_unconfirmed') is False and
            source.sha(source.private(folder / '003-stdout.private.log')) == child['stdout_sha256'] and
            source.sha(source.private(folder / '003-stderr.private.log')) == child['stderr_sha256'],
            'Saved failed child or supervisor log hashes changed')
    marker = json.loads(source.private(folder / '003-child-started.private.json'))
    intent = rows[-2]
    require(marker.get('task_index') == 3 and marker.get('child_pid') == child['child_pid'] and
            marker.get('parent_pid') == intent['supervisor_pid'] and
            marker.get('pending_intent_sha256') == intent['entry_sha256'] and
            marker.get('permit_sha256') == intent['permit_sha256'] and
            marker.get('source_freeze_sha256') == source.sha(source.private(freeze)) and
            marker.get('same_intent_replay_authorized') is False and
            intent.get('plan_sha256') == plan_sha and
            intent.get('package_sha256') == plan['task_roster'][3]['package_sha256'],
            'Failed one-use child/source/package/plan binding changed')
    receipt_folder = root / 'controls/attempts/003/positive-1'
    receipt = json.loads(source.private(receipt_folder / 'receipt.json'))
    after = json.loads(source.private(receipt_folder / 'after-persisted-state.json'))
    body = copy.deepcopy(after); digest = body.pop('business_sha256')
    require(source.sha(factory.canonical(body)) == digest, 'Saved positive DB/Git digest changed')
    with scoped.cohort_context(value):
        task = gui_controls._task(plan['task_roster'][3]['task_id'])  # Already consumed trusted control only.
        identity = plan['task_roster'][3]
        package = {'world_sha256': plan['world_sha256'], 'baseline_business_sha256': baseline['business_sha256'],
                   'native_acl_sha256': plan['native_acl_sha256'], 'task': task}
        require(source.sha(factory.canonical(task)) == identity['task_object_sha256'] and
                source.sha(factory.canonical(package)) == identity['package_sha256'],
                'Consumed positive task/package/baseline/ACL binding changed')
        verdict = verify.evaluate_final_task(task, baseline, after, inspect_live_git=False)
    require(verdict == receipt['persisted_oracle'] and verdict.get('score') == 1.0 and
            verdict.get('no_regression') is True and verdict.get('persisted_oracle') is True and
            receipt.get('fresh_browser_context') is True and receipt.get('scoped_non_admin_operator') is True and
            receipt.get('model_calls') == 0 and receipt.get('credential_retained_in_receipt') is False and
            receipt.get('raw_har_retained') is False and receipt['gui'].get('saved_visible') is True,
            'Retained first positive semantics or GUI scope changed')
    pngs = sorted(receipt_folder.glob('*.png'))
    require(len(pngs) == 5, 'Failed positive expected five raw GUI images')
    for png in pngs:
        raw = source.private(png)
        with Image.open(BytesIO(raw)) as image:
            require(image.format == 'PNG' and image.width == 1440 and image.height >= 1000,
                    'Retained native PNG format/viewport changed')
    for field, name in [('policy_screenshot_sha256', 'policy.png'), ('member_screenshot_sha256', 'members-after.png')]:
        require(receipt['gui'][field] == source.sha(source.private(receipt_folder / name)), 'Saved GUI image hash changed')
    require(not (receipt_folder / 'after-reset-persisted-state.json').exists() and
            not (receipt_folder / 'case-complete.private.json').exists() and
            not (receipt_folder.parent / 'trio-complete.private.json').exists() and
            not (folder / '003-child-result.private.json').exists(),
            'Historical failed control must not gain later completion evidence')
    evidence = result['cleanup']['forensics']; hashes = evidence['raw_file_sha256s']
    candidates = []
    for directory in (root / 'startup-forensics').iterdir():
        path = directory / 'docker-state.stdout.private.json'
        if directory.is_dir() and path.exists() and source.sha(source.private(path)) == hashes['docker_state_stdout']:
            candidates.append(directory)
    require(candidates, 'Retained pre-cleanup failed state unavailable')
    boot_folder = next((p for p in candidates if p.name.startswith('failed-create-')), candidates[0])
    names = {'docker_logs_stdout': 'docker-logs.stdout.private.log', 'docker_logs_stderr': 'docker-logs.stderr.private.log',
             'docker_state_stdout': 'docker-state.stdout.private.json', 'docker_state_stderr': 'docker-state.stderr.private.log'}
    retained = {key: source.private(boot_folder / name) for key, name in names.items()}
    require({key: source.sha(raw) for key, raw in retained.items()} == hashes, 'Raw startup evidence changed')
    cause = classify_boot(json.loads(retained['docker_state_stdout']), retained['docker_logs_stdout'], retained['docker_logs_stderr'])
    terminal = json.loads(source.private(detached / 'worker-terminal.private.json'))
    require(terminal.get('exit_code') == 0 and terminal.get('automatic_restarts') == 0 and
            terminal['stdout_sha256'] == source.sha(source.private(detached / 'worker.stdout.private.log')) and
            terminal['stderr_sha256'] == source.sha(source.private(detached / 'worker.stderr.private.log')),
            'Detached supervisor terminal/log hashes changed')
    detached_result = json.loads(source.private(detached / 'worker.stdout.private.log'))
    require(detached_result.get('status') == 'terminal_prospective_control_failure_no_replay' and
            detached_result.get('new_baseline_controls_completed') == 3,
            'Detached exit zero must not imply all controls succeeded')
    manifest = {str(p.relative_to(root)): source.sha(source.private(p))
                for p in sorted(root.rglob('*')) if p.is_file()}
    private = {'schema': 'envloop-gitlab-prospective-v5-terminal-independent-private-v1',
               'source_freeze_sha256': source.sha(source.private(freeze)), 'plan_sha256': plan_sha,
               'journal_sha256': source.sha(source.private(root / 'controls/journal.private.jsonl')),
               'prefix': prefix, 'failed_index': 3, 'failed_positive_semantic_score': 1.0,
               'failed_positive_no_regression': True, 'failed_positive_completion_claim': False,
               'failed_positive_png_sha256s': {p.name: source.sha(source.private(p)) for p in pngs},
               'child': child, 'cause': cause, 'retained_startup_raw_sha256s': hashes,
               'cleanup_saved_exact_baseline_assertion': result['cleanup'].get('exact_baseline'),
               'cleanup_independent_raw_sql_git_snapshot_available': False,
               'epoch_file_sha256s': manifest, 'detached_terminal_sha256': source.sha(source.private(detached / 'worker-terminal.private.json')),
               'same_intent_replay_authorized': False, 'application_mutations': 0, 'provider_calls': 0,
               'model_calls': 0, 'official_final_admitted': 0}
    digest = source.write_new(out, private)
    public = {'schema': 'envloop-gitlab-prospective-v5-terminal-independent-public-v1',
              'status': 'terminal_post_positive_cold_reset_failure_no_replay',
              'private_review_sha256': digest, 'source_freeze_sha256': private['source_freeze_sha256'],
              'cohort_plan_sha256': plan_sha, 'journal_sha256': private['journal_sha256'],
              'new_baseline_controls_independently_reopened': 3, 'completed_control_indices': [0, 1, 2],
              'failed_control_index': 3, 'pending_intent': False, 'new_baseline_projects': 32,
              'source_families': 20, 'prospective_denominator': 100,
              'failed_positive_semantic_score': 1.0, 'failed_positive_no_regression': True,
              'failed_positive_gui_pngs': 5, 'failed_positive_is_completed_control': False,
              'failed_reset_and_trio_completion_absent': True, 'epoch_files_reopened': len(manifest),
              'retained_startup_raw_sha256s': hashes, 'child_exit_code': 1,
              'child_timed_out': False, 'child_process_group_terminated': True,
              'detached_supervisor_exit_code': 0, 'detached_exit_zero_is_success': False,
              'cleanup_saved_exact_baseline_assertion': result['cleanup'].get('exact_baseline'),
              'cleanup_independent_raw_sql_git_snapshot_available': False,
              **cause, 'historical_controls_transferred': 0, 'same_intent_replay_authorized': False,
              'live_docker_calls': 0, 'application_mutations': 0, 'provider_calls': 0,
              'model_calls': 0, 'official_final_admitted': 0}
    source.write_new(public_out, public, 0o644)
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ['freeze', 'detached', 'private-out', 'public-out']:
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(freeze=args.freeze, detached=args.detached, out=args.private_out,
                           public_out=args.public_out), sort_keys=True))


if __name__ == '__main__':
    main()
