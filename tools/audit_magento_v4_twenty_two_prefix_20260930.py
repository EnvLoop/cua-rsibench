"""Read-only independent audit of the first 22 frozen Magento v4 controls.

The fifth bounded chunk adds cases 17 through 21 to the previously audited
seventeen-case prefix. This module reopens private saved-state and native
process evidence. It never dispatches a task or calls a model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import audit_magento_v4_seven_prefix_20260929 as seven
from tools import audit_magento_v4_seventeen_prefix_20260929 as seventeen
from tools import audit_magento_v4_twelve_prefix_20260929 as twelve
from tools import magento_clean_100_v4 as v4


SCHEMA = 'envloop-magento-v4-twenty-two-prefix-independent-audit-public-v1'
OLD_BOUNDARY = seventeen.PREFIX_ROWS
PREFIX_ROWS = 707
COMPLETED_COUNT = 22
NEW_COUNT = 5
AUDIT_ERROR = first.AuditError


def read_twenty_two_prefix(path: Path) -> tuple[list[dict], bytes]:
    first.must(path.is_file() and not path.is_symlink(),
               'missing or linked private journal')
    lines = path.read_bytes().splitlines(keepends=True)
    first.must(len(lines) >= PREFIX_ROWS,
               'fifth bounded chunk is incomplete')
    lines = lines[:PREFIX_ROWS]
    first.must(all(line.endswith(b'\n') for line in lines),
               'truncated twenty-two-case journal prefix')
    previous = '0' * 64
    rows = []
    for sequence, line in enumerate(lines):
        row = json.loads(line)
        first.must(isinstance(row, dict) and line == first.canonical(row) and
                   row.get('schema') == v4.JOURNAL_SCHEMA and
                   row.get('sequence') == sequence and
                   row.get('previous_line_sha256') == previous,
                   'noncanonical or broken append-only journal')
        rows.append(row)
        previous = first.sha(line)
    first.must(rows[-1].get('event') == 'chunk_completed',
               'twenty-two-case prefix is not a completed chunk')
    return rows, b''.join(lines)


def check_fifth_chunk(rows: list[dict], cases: list[dict],
                      freeze: dict, freeze_sha: str) -> dict:
    first.must(len(rows) == PREFIX_ROWS and len(cases) == 100,
               'wrong fifth-chunk journal or frozen plan cardinality')
    earlier = seventeen.check_seventeen_chunks(
        rows[:OLD_BOUNDARY], cases, freeze, freeze_sha)
    dispatch, final = rows[OLD_BOUNDARY], rows[-1]
    first.must(dispatch.get('event') == 'dispatch_started' and
               dispatch.get('max_cases') == NEW_COUNT and
               dispatch.get('completed_before_dispatch') == 17 and
               dispatch.get('freeze_v4_sha256') == freeze_sha and
               dispatch.get('parent_v3_freeze_sha256') ==
               freeze['parent_v3_freeze_sha256'] and
               dispatch.get('model_calls') ==
               dispatch.get('official_final_admitted') == 0,
               'fifth bounded dispatch changed')
    starts = [r for r in rows if r.get('event') == 'case_attempt_started']
    completed = [r for r in rows if r.get('event') == 'case_completed']
    stopped = [r for r in rows if r.get('event') == 'attempt_stopped']
    reconciled = [r for r in rows if r.get('event') == 'attempt_reconciled']
    first.must([(r.get('index'), r.get('attempt')) for r in starts] ==
               [(0, 0), (0, 1)] +
               [(index, 0) for index in range(1, COMPLETED_COUNT)] and
               [(r.get('index'), r.get('attempt')) for r in completed] ==
               [(0, 1)] +
               [(index, 0) for index in range(1, COMPLETED_COUNT)] and
               [(r.get('index'), r.get('attempt')) for r in stopped] ==
               [(0, 0)] and
               [(r.get('index'), r.get('attempt')) for r in reconciled] ==
               [(0, 0)] and
               all(r.get('task_id') == cases[r['index']]['task_id'] and
                   r.get('package_sha256') == cases[r['index']]['package_sha256']
                   for r in starts) and
               all(r.get('model_calls') == r.get('official_final_admitted') == 0
                   for r in starts + stopped + reconciled + completed),
               'ordered attempt identities or sole same-ID retry changed')
    fifth = rows[OLD_BOUNDARY + 1:-1]
    first.must(len(fifth) == NEW_COUNT * 31 and
               all(r.get('index') in range(17, COMPLETED_COUNT) and
                   r.get('attempt') == 0 for r in fifth) and
               sum(r.get('event') == 'dispatch_started' for r in rows) == 5 and
               sum(r.get('event') == 'chunk_completed' for r in rows) == 5 and
               sum(r.get('event') == 'run_started' for r in rows) == 1,
               'fifth chunk contains foreign, duplicated or missing events')
    receipts = [r['calibration_sha256'] for r in completed]
    first.must(final.get('max_cases') == NEW_COUNT and
               final.get('dispatch_sequence') == dispatch['sequence'] and
               final.get('freeze_v4_sha256') == freeze_sha and
               final.get('parent_v3_freeze_sha256') ==
               freeze['parent_v3_freeze_sha256'] and
               final.get('completed_distinct_cases') == COMPLETED_COUNT and
               final.get('newly_completed_this_dispatch') == NEW_COUNT and
               final.get('ordered_completed_task_identity_sha256') ==
               v4.case_identity_digest(cases[:COMPLETED_COUNT]) and
               final.get('completed_calibration_receipts_sha256') ==
               first.sha(('\n'.join(receipts) + '\n').encode()) and
               final.get('journal_prefix_sha256') ==
               first.sha(b''.join(first.canonical(r) for r in rows[:-1])) and
               final.get('infrastructure_retries') == 1 and
               final.get('infrastructure_retries') <=
               freeze['study_wide_infrastructure_retry_cap'] and
               final.get('model_calls') ==
               final.get('official_final_admitted') == 0,
               'fifth chunk receipt or frozen retry budget changed')
    return {'dispatches': (*earlier['dispatches'], dispatch),
            'chunks': (*earlier['chunks'], final),
            'completed': completed}


PUBLIC_FIELDS = {
    'schema', 'date', 'status', 'independent_auditor_source_sha256',
    'shared_seventeen_case_auditor_source_sha256',
    'shared_twelve_case_auditor_source_sha256',
    'shared_seven_case_auditor_source_sha256',
    'shared_two_case_auditor_source_sha256',
    'source_freeze_sha256', 'source_commit', 'plan_sha256',
    'ordered_task_identity_sha256',
    'preconfig_amendment_freeze_sha256',
    'preconfig_cleanup_receipt_sha256',
    'seventeen_case_journal_prefix_sha256',
    'twenty_two_case_journal_prefix_sha256',
    'fifth_chunk_receipt_sha256',
    'completed_calibration_receipts_sha256',
    'planned_distinct_candidate_controls',
    'previously_audited_candidate_controls',
    'new_candidate_controls_independently_audited',
    'completed_distinct_candidate_controls',
    'positive_saved_state_pass', 'wrong_variant_saved_state_rejected',
    'fresh_clone_material_reset_pass',
    'successful_step_process_receipts_reopened',
    'new_step_process_receipts_reopened', 'pair_cleanup_verified_events',
    'failed_preconfig_infrastructure_attempts',
    'reconciled_same_id_infrastructure_retries',
    'study_wide_infrastructure_retry_cap',
    'invalid_attempts_by_classification',
    'live_disposable_pair_absence_checked',
    'historical_v2_v3_controls_reused',
    'model_calls', 'official_final_admitted',
}


def audit_twenty_two(repo_root: Path, run_dir: Path) -> dict:
    root, run = repo_root.resolve(), run_dir.resolve()
    first.must(run == root / first.RUN_REL and run.is_dir() and
               not run_dir.is_symlink(),
               'audit requires exact original private v4 run directory')
    plan, source, cron, freeze_file = (
        root / first.PLAN_REL, root / first.SOURCE_REL,
        root / first.CRON_FREEZE_REL, root / first.V4_FREEZE_REL)
    freeze, old, freeze_sha = first.validate_source_bindings(
        root, plan, source, cron, freeze_file)
    cases = first.validate_plan(plan, freeze['plan_sha256'])
    first.must(v4.case_identity_digest(cases) ==
               freeze['ordered_task_identity_sha256'],
               'ordered frozen candidate identity changed')
    rows, prefix_raw = read_twenty_two_prefix(run / 'journal.private.jsonl')
    boundaries = check_fifth_chunk(rows, cases, freeze, freeze_sha)
    v4.validate_run_header(rows, freeze_sha, freeze)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, freeze, freeze_sha)
    published_seventeen, _ = first.read_json(
        root / 'docs/evidence/magento-v4-first-seventeen-independent-audit-2026-09-29.json')
    old_prefix = b''.join(prefix_raw.splitlines(keepends=True)[:OLD_BOUNDARY])
    first.must(published_seventeen.get('seventeen_case_journal_prefix_sha256') ==
               first.sha(old_prefix) and
               published_seventeen.get('fourth_chunk_receipt_sha256') ==
               first.sha(first.canonical(boundaries['chunks'][3])),
               'prior seventeen-case public receipt no longer binds prefix')
    expected_attempts = {'case-000-attempt-0', 'case-000-attempt-1'} | {
        f'case-{index:03d}-attempt-0' for index in range(1, COMPLETED_COUNT)}
    first.must(all((run / 'attempts' / name).is_dir() and
                   not (run / 'attempts' / name).is_symlink()
                   for name in expected_attempts),
               'one of the twenty-two journaled attempt directories is missing')
    retry = first.check_preconfig_retry(
        root, run, rows, cases[0], freeze_sha)
    receipts = []
    for index in range(COMPLETED_COUNT):
        attempt = 1 if index == 0 else 0
        seven.check_process_receipts(run, rows, index, attempt)
        receipts.append(first.check_successful_case(
            run, rows, index, attempt, cases[index],
            old['runtime_fingerprint_sha256']))
    first.must([r['calibration_sha256'] for r in boundaries['completed']] ==
               receipts,
               'independently replayed calibrations differ from journal')
    report = {
        'schema': SCHEMA, 'date': '2026-09-30',
        'status': 'twenty_two_v4_evaluator_controls_independently_audited_no_final_admissions',
        'independent_auditor_source_sha256': first.sha(Path(__file__).read_bytes()),
        'shared_seventeen_case_auditor_source_sha256':
            first.sha(Path(seventeen.__file__).read_bytes()),
        'shared_twelve_case_auditor_source_sha256':
            first.sha(Path(twelve.__file__).read_bytes()),
        'shared_seven_case_auditor_source_sha256':
            first.sha(Path(seven.__file__).read_bytes()),
        'shared_two_case_auditor_source_sha256':
            first.sha(Path(first.__file__).read_bytes()),
        'source_freeze_sha256': freeze_sha,
        'source_commit': freeze['source_commit'],
        'plan_sha256': freeze['plan_sha256'],
        'ordered_task_identity_sha256': freeze['ordered_task_identity_sha256'],
        'preconfig_amendment_freeze_sha256': retry['supplement_sha256'],
        'preconfig_cleanup_receipt_sha256': retry['reconciliation_sha256'],
        'seventeen_case_journal_prefix_sha256':
            published_seventeen['seventeen_case_journal_prefix_sha256'],
        'twenty_two_case_journal_prefix_sha256': first.sha(prefix_raw),
        'fifth_chunk_receipt_sha256':
            first.sha(first.canonical(boundaries['chunks'][4])),
        'completed_calibration_receipts_sha256':
            boundaries['chunks'][4]['completed_calibration_receipts_sha256'],
        'planned_distinct_candidate_controls': 100,
        'previously_audited_candidate_controls': 17,
        'new_candidate_controls_independently_audited': NEW_COUNT,
        'completed_distinct_candidate_controls': COMPLETED_COUNT,
        'positive_saved_state_pass': COMPLETED_COUNT,
        'wrong_variant_saved_state_rejected': COMPLETED_COUNT,
        'fresh_clone_material_reset_pass': COMPLETED_COUNT,
        'successful_step_process_receipts_reopened':
            COMPLETED_COUNT * len(first.ORIGINAL_STEPS),
        'new_step_process_receipts_reopened':
            NEW_COUNT * len(first.ORIGINAL_STEPS),
        'pair_cleanup_verified_events': COMPLETED_COUNT * 2,
        'failed_preconfig_infrastructure_attempts': 1,
        'reconciled_same_id_infrastructure_retries': 1,
        'study_wide_infrastructure_retry_cap':
            freeze['study_wide_infrastructure_retry_cap'],
        'invalid_attempts_by_classification': {retry['classification']: 1},
        'live_disposable_pair_absence_checked': False,
        'historical_v2_v3_controls_reused': 0,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    first.must(set(report) == PUBLIC_FIELDS,
               'public report field allowlist changed')
    return report


def render_markdown(report: dict) -> str:
    first.must(set(report) == PUBLIC_FIELDS,
               'unexpected public report fields')
    return (
        '# Magento v4: independent audit of the first 22 controls\n\n'
        'The fifth bounded chunk adds **5** original-Magento evaluator GUI '
        'controls to the previously audited 17-case prefix. The frozen '
        '100-case plan now has **22/100** completed evaluator controls. '
        'All 22 saved-state positives score 1, wrong-variant controls score '
        '0, and fresh-clone material resets pass replay against retained SQL '
        'and search snapshots. The audit reopened 286 successful native-step '
        'process receipts, including 65 in the new chunk, and 44 '
        'pair-cleanup events. This is evaluator calibration only: **0 model '
        'calls and 0 official final tasks admitted**.\n\n'
        'The fifth chunk contains one attempt per new case and no new '
        'infrastructure retry. The sole earlier before-seed, before-GUI '
        'startup failure remains reconciled under its frozen same-ID retry. '
        'The 17-case prefix, fifth chunk, and complete 22-case journal '
        'prefix are hash-bound in the adjacent JSON. Later journal appends '
        'cannot change this prefix. Live disposable-pair absence was not '
        'checked by this saved-evidence auditor.\n\n'
        'Historical v2/v3 controls contribute zero. The remaining 78 '
        'controls, per-task final admission, researcher campaigns, and '
        'model final outcomes are not established here. Raw task and saved '
        'state files stay in private evaluator storage for authorized replay.\n'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--public-json', type=Path)
    parser.add_argument('--public-md', type=Path)
    args = parser.parse_args()
    first.must((args.public_json is None) == (args.public_md is None),
               'JSON and Markdown public outputs must be requested together')
    report = audit_twenty_two(args.repo_root, args.run_dir)
    if args.public_json is not None:
        public_dir = (Path(__file__).resolve().parents[1] /
                      'docs/evidence').resolve()
        for target in (args.public_json, args.public_md):
            target = target.resolve()
            first.must(target.is_relative_to(public_dir) and
                       not target.exists(),
                       'public outputs must be new files under auditor docs/evidence')
        args.public_json.parent.mkdir(parents=True, exist_ok=True)
        args.public_json.write_text(
            json.dumps(report, indent=2, sort_keys=True) + '\n',
            encoding='utf-8')
        args.public_md.write_text(render_markdown(report), encoding='utf-8')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
