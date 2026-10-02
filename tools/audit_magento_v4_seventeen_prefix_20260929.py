"""Read-only audit of the first seventeen frozen Magento v4 controls.

The four complete bounded chunks (2 + 5 + 5 + 5) form an immutable journal
prefix. This auditor reopens all saved-state, native reset, process, source,
and cleanup receipts. It never contacts Docker, dispatches a task, or calls a
model. Later journal appends cannot change this prefix's hash-bound result.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import audit_magento_v4_seven_prefix_20260929 as seven
from tools import audit_magento_v4_twelve_prefix_20260929 as twelve
from tools import magento_clean_100_v4 as v4


SCHEMA = 'envloop-magento-v4-seventeen-prefix-independent-audit-public-v1'
THIRD_BOUNDARY = twelve.PREFIX_ROWS
PREFIX_ROWS = 550
COMPLETED_COUNT = 17
AUDIT_ERROR = first.AuditError


def read_seventeen_prefix(path: Path) -> tuple[list[dict], bytes]:
    first.must(path.is_file() and not path.is_symlink(), 'missing private journal')
    lines = path.read_bytes().splitlines(keepends=True)
    first.must(len(lines) >= PREFIX_ROWS, 'fourth bounded chunk is incomplete')
    lines = lines[:PREFIX_ROWS]
    first.must(all(line.endswith(b'\n') for line in lines),
               'truncated seventeen-case journal prefix')
    previous = '0' * 64
    rows = []
    for sequence, line in enumerate(lines):
        row = json.loads(line)
        first.must(isinstance(row, dict) and line == first.canonical(row) and
                   row.get('schema') == v4.JOURNAL_SCHEMA and
                   row.get('sequence') == sequence and
                   row.get('previous_line_sha256') == previous,
                   'noncanonical or broken append-only seventeen-case journal')
        rows.append(row)
        previous = first.sha(line)
    first.must(rows[-1].get('event') == 'chunk_completed',
               'seventeen-case prefix is not a complete bounded chunk')
    return rows, b''.join(lines)


def check_seventeen_chunks(rows: list[dict], cases: list[dict], freeze: dict,
                           freeze_sha: str) -> dict:
    first.must(len(rows) == PREFIX_ROWS and len(cases) == 100,
               'not the exact four-chunk seventeen-case prefix')
    earlier = twelve.check_twelve_chunks(
        rows[:THIRD_BOUNDARY], cases, freeze, freeze_sha)
    dispatch, final = rows[THIRD_BOUNDARY], rows[-1]
    first.must(dispatch.get('event') == 'dispatch_started' and
               dispatch.get('max_cases') == 5 and
               dispatch.get('completed_before_dispatch') == 12 and
               dispatch.get('freeze_v4_sha256') == freeze_sha and
               dispatch.get('parent_v3_freeze_sha256') ==
               freeze['parent_v3_freeze_sha256'] and
               dispatch.get('model_calls') ==
               dispatch.get('official_final_admitted') == 0,
               'fourth bounded dispatch changed')
    starts = [r for r in rows if r.get('event') == 'case_attempt_started']
    completions = [r for r in rows if r.get('event') == 'case_completed']
    stopped = [r for r in rows if r.get('event') == 'attempt_stopped']
    reconciled = [r for r in rows if r.get('event') == 'attempt_reconciled']
    first.must([(r.get('index'), r.get('attempt')) for r in starts] ==
               [(0, 0), (0, 1)] +
               [(index, 0) for index in range(1, COMPLETED_COUNT)] and
               [(r.get('index'), r.get('attempt')) for r in completions] ==
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
                   for r in starts + stopped + reconciled + completions),
               'ordered completed cases or sole same-ID retry changed')
    fourth = rows[THIRD_BOUNDARY + 1:-1]
    first.must(sum(r.get('event') == 'dispatch_started' for r in rows) == 4 and
               sum(r.get('event') == 'chunk_completed' for r in rows) == 4 and
               sum(r.get('event') == 'run_started' for r in rows) == 1 and
               len(fourth) == 5 * 31 and
               all(r.get('index') in range(12, COMPLETED_COUNT) and
                   r.get('attempt') == 0 for r in fourth),
               'fourth chunk contains a foreign, duplicated, or missing event')
    receipts = [r['calibration_sha256'] for r in completions]
    first.must(final.get('max_cases') == 5 and
               final.get('dispatch_sequence') == dispatch['sequence'] and
               final.get('freeze_v4_sha256') == freeze_sha and
               final.get('parent_v3_freeze_sha256') ==
               freeze['parent_v3_freeze_sha256'] and
               final.get('completed_distinct_cases') == COMPLETED_COUNT and
               final.get('newly_completed_this_dispatch') == 5 and
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
               'fourth chunk receipt or retry budget does not bind prefix')
    return {'dispatches': (*earlier['dispatches'], dispatch),
            'chunks': (*earlier['chunks'], final), 'completed': completions}


def audit_seventeen(repo_root: Path, run_dir: Path) -> dict:
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
    rows, prefix_raw = read_seventeen_prefix(run / 'journal.private.jsonl')
    boundaries = check_seventeen_chunks(rows, cases, freeze, freeze_sha)
    # Frozen-runner validators corroborate the independently replayed checks.
    v4.validate_run_header(rows, freeze_sha, freeze)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, freeze, freeze_sha)
    expected_attempts = {'case-000-attempt-0', 'case-000-attempt-1'} | {
        f'case-{index:03d}-attempt-0' for index in range(1, COMPLETED_COUNT)}
    first.must(all((run / 'attempts' / name).is_dir() and
                   not (run / 'attempts' / name).is_symlink()
                   for name in expected_attempts),
               'one of the seventeen journaled attempt directories is missing')
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
               'seventeen independently replayed calibrations differ from journal')
    report = {
        'schema': SCHEMA,
        'date': '2026-09-29',
        'status': 'seventeen_v4_evaluator_controls_independently_audited_no_final_admissions',
        'independent_auditor_source_sha256': first.sha(Path(__file__).read_bytes()),
        'shared_twelve_case_auditor_source_sha256': first.sha(Path(twelve.__file__).read_bytes()),
        'shared_seven_case_auditor_source_sha256': first.sha(Path(seven.__file__).read_bytes()),
        'shared_two_case_auditor_source_sha256': first.sha(Path(first.__file__).read_bytes()),
        'source_freeze_sha256': freeze_sha,
        'source_commit': freeze['source_commit'],
        'plan_sha256': freeze['plan_sha256'],
        'ordered_task_identity_sha256': freeze['ordered_task_identity_sha256'],
        'preconfig_amendment_freeze_sha256': retry['supplement_sha256'],
        'preconfig_cleanup_receipt_sha256': retry['reconciliation_sha256'],
        'seventeen_case_journal_prefix_sha256': first.sha(prefix_raw),
        'first_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][0])),
        'second_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][1])),
        'third_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][2])),
        'fourth_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][3])),
        'completed_calibration_receipts_sha256': boundaries['chunks'][3][
            'completed_calibration_receipts_sha256'],
        'planned_distinct_candidate_controls': 100,
        'completed_distinct_candidate_controls': COMPLETED_COUNT,
        'positive_saved_state_pass': COMPLETED_COUNT,
        'wrong_variant_saved_state_rejected': COMPLETED_COUNT,
        'fresh_clone_material_reset_pass': COMPLETED_COUNT,
        'successful_step_process_receipts_reopened': COMPLETED_COUNT * len(first.ORIGINAL_STEPS),
        'pair_cleanup_verified_events': COMPLETED_COUNT * 2,
        'failed_preconfig_infrastructure_attempts': 1,
        'reconciled_same_id_infrastructure_retries': 1,
        'study_wide_infrastructure_retry_cap': freeze['study_wide_infrastructure_retry_cap'],
        'invalid_attempts_by_classification': {retry['classification']: 1},
        'live_disposable_pair_absence_checked': False,
        'historical_v2_v3_controls_reused': 0,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
    first.must(set(report) == PUBLIC_FIELDS, 'public output field allowlist changed')
    return report


PUBLIC_FIELDS = {
    'schema', 'date', 'status', 'independent_auditor_source_sha256',
    'shared_twelve_case_auditor_source_sha256',
    'shared_seven_case_auditor_source_sha256',
    'shared_two_case_auditor_source_sha256',
    'source_freeze_sha256', 'source_commit', 'plan_sha256',
    'ordered_task_identity_sha256', 'preconfig_amendment_freeze_sha256',
    'preconfig_cleanup_receipt_sha256',
    'seventeen_case_journal_prefix_sha256',
    'first_chunk_receipt_sha256', 'second_chunk_receipt_sha256',
    'third_chunk_receipt_sha256', 'fourth_chunk_receipt_sha256',
    'completed_calibration_receipts_sha256',
    'planned_distinct_candidate_controls', 'completed_distinct_candidate_controls',
    'positive_saved_state_pass', 'wrong_variant_saved_state_rejected',
    'fresh_clone_material_reset_pass', 'successful_step_process_receipts_reopened',
    'pair_cleanup_verified_events', 'failed_preconfig_infrastructure_attempts',
    'reconciled_same_id_infrastructure_retries',
    'study_wide_infrastructure_retry_cap', 'invalid_attempts_by_classification',
    'live_disposable_pair_absence_checked', 'historical_v2_v3_controls_reused',
    'model_calls', 'official_final_admitted',
}


def render_markdown(report: dict) -> str:
    first.must(set(report) == PUBLIC_FIELDS, 'unexpected public report fields')
    return (
        '# Magento v4: independent audit of the first seventeen controls\n\n'
        'The first four complete bounded chunks contain **17 of 100** '
        'planned, ordered original-Magento evaluator GUI controls. All '
        'seventeen saved-state positives score 1, wrong-variant controls '
        'score 0, and fresh-clone material resets pass independent replay '
        'against retained SQL and search snapshots. All 221 successful step '
        'process receipts and 34 pair-cleanup journal events were reopened. '
        'This is evaluator calibration only: **0 model calls and 0 official '
        'final tasks admitted**.\n\n'
        'The first case had one before-seed, before-GUI HTTP startup failure. '
        'Its exact disposable pair was retired under a source-frozen '
        'reconciliation receipt, followed by one same-ID retry. The '
        'seventeen-case journal prefix and all four bounded chunk receipts '
        'are hash-bound in the adjacent JSON. Later journal appends do not '
        'change this prefix. The single retry is below the frozen study-wide '
        'cap of 20. Live container absence was not checked by this read-only '
        'auditor.\n\n'
        'Historical v2/v3 controls contribute zero. The remaining 83 '
        'controls, per-task final admission, researcher campaigns, and model '
        'final outcomes are not established here. Raw task and saved-state '
        'files stay in private evaluator storage for authorized replay.\n'
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
    report = audit_seventeen(args.repo_root, args.run_dir)
    if args.public_json is not None:
        public_dir = (Path(__file__).resolve().parents[1] /
                      'docs/evidence').resolve()
        for target in (args.public_json, args.public_md):
            target = target.resolve()
            first.must(target.is_relative_to(public_dir) and
                       not target.exists(),
                       'new public output must be under auditor checkout docs/evidence')
        args.public_json.parent.mkdir(parents=True, exist_ok=True)
        args.public_json.write_text(json.dumps(report, indent=2, sort_keys=True) +
                                    '\n', encoding='utf-8')
        args.public_md.write_text(render_markdown(report), encoding='utf-8')
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main()
