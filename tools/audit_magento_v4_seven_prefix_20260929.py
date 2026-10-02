"""Read-only audit of the first seven frozen Magento v4 evaluator controls.

This checks the two complete bounded chunks (2 + 5) as an immutable journal
prefix, so later campaign append operations do not invalidate this receipt.
It replays every saved-state score and reset from private evidence. It does
not contact Docker, start a process, or dispatch a model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools import audit_magento_v4_partial_batch_20260929 as first
from tools import magento_clean_100_v4 as v4


SCHEMA = 'envloop-magento-v4-seven-prefix-independent-audit-public-v1'
PREFIX_ROWS = 236
FIRST_BOUNDARY = 79
COMPLETED_COUNT = 7
AUDIT_ERROR = first.AuditError


def read_seven_prefix(path: Path) -> tuple[list[dict], bytes]:
    first.must(path.is_file() and not path.is_symlink(), 'missing private journal')
    lines = path.read_bytes().splitlines(keepends=True)
    first.must(len(lines) >= PREFIX_ROWS, 'second bounded chunk is incomplete')
    lines = lines[:PREFIX_ROWS]
    first.must(all(line.endswith(b'\n') for line in lines),
               'truncated seven-case journal prefix')
    prior = '0' * 64
    rows = []
    for number, line in enumerate(lines):
        row = json.loads(line)
        first.must(isinstance(row, dict) and line == first.canonical(row) and
                   row.get('schema') == v4.JOURNAL_SCHEMA and
                   row.get('sequence') == number and
                   row.get('previous_line_sha256') == prior,
                   'noncanonical or broken append-only seven-case journal')
        rows.append(row)
        prior = first.sha(line)
    first.must(rows[-1].get('event') == 'chunk_completed',
               'seven-case prefix is not a complete bounded chunk')
    return rows, b''.join(lines)


def check_seven_chunks(rows: list[dict], cases: list[dict], freeze: dict,
                       freeze_sha: str) -> dict:
    first.must(len(rows) == PREFIX_ROWS and len(cases) == 100,
               'not the exact two-chunk seven-case prefix')
    first.check_chunk(rows[:FIRST_BOUNDARY], cases, freeze, freeze_sha)
    dispatch = rows[FIRST_BOUNDARY]
    final = rows[-1]
    starts = [r for r in rows if r.get('event') == 'case_attempt_started']
    completions = [r for r in rows if r.get('event') == 'case_completed']
    stopped = [r for r in rows if r.get('event') == 'attempt_stopped']
    reconciled = [r for r in rows if r.get('event') == 'attempt_reconciled']
    first.must(dispatch.get('event') == 'dispatch_started' and
               dispatch.get('max_cases') == 5 and
               dispatch.get('completed_before_dispatch') == 2 and
               dispatch.get('freeze_v4_sha256') == freeze_sha and
               dispatch.get('parent_v3_freeze_sha256') ==
               freeze['parent_v3_freeze_sha256'] and
               dispatch.get('model_calls') ==
               dispatch.get('official_final_admitted') == 0,
               'second bounded dispatch changed')
    first.must([(r.get('index'), r.get('attempt')) for r in starts] ==
               [(0, 0), (0, 1)] + [(index, 0) for index in range(1, 7)] and
               [(r.get('index'), r.get('attempt')) for r in completions] ==
               [(0, 1)] + [(index, 0) for index in range(1, 7)] and
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
    first.must(sum(r.get('event') == 'dispatch_started' for r in rows) == 2 and
               sum(r.get('event') == 'chunk_completed' for r in rows) == 2 and
               sum(r.get('event') == 'run_started' for r in rows) == 1 and
               all(r.get('index') in range(2, 7) and
                   r.get('attempt') == 0
                   for r in rows[FIRST_BOUNDARY + 1:-1]),
               'second chunk contains a foreign or duplicated case event')
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
               final.get('model_calls') ==
               final.get('official_final_admitted') == 0,
               'second chunk receipt does not bind the seven-case prefix')
    return {'dispatches': (rows[1], dispatch),
            'chunks': (rows[FIRST_BOUNDARY - 1], final),
            'completed': completions}


def check_process_receipts(run: Path, rows: list[dict], index: int,
                           attempt: int) -> None:
    """Reopen every successful process receipt and match its journal values."""
    base = (run / 'attempts' / f'case-{index:03d}-attempt-{attempt}' /
            f'case-{index:03d}')
    finishes = [r for r in rows if r.get('event') == 'step_finished' and
                r.get('index') == index and r.get('attempt') == attempt]
    first.must([r.get('step') for r in finishes] == list(first.ORIGINAL_STEPS),
               'completed attempt has a missing or reordered step')
    for row in finishes:
        step = row['step']
        pair = 'negative' if step.startswith('negative-') or step == 'fresh-reset' \
            else 'positive'
        process, _ = first.read_json(
            base / pair / f'{step}-process.private.json')
        first.must(all(process.get(key) == row.get(key) for key in (
            'exit_code', 'stdout_sha256', 'stdout_bytes',
            'stderr_sha256', 'stderr_bytes')) and
            row.get('exit_code') == 0,
            'saved process receipt disagrees with successful journal step')


def audit_seven(repo_root: Path, run_dir: Path) -> dict:
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
    rows, prefix_raw = read_seven_prefix(run / 'journal.private.jsonl')
    boundaries = check_seven_chunks(rows, cases, freeze, freeze_sha)
    # Frozen runner checks are extra corroboration. The checks and replays
    # above and below are the independent acceptance path.
    v4.validate_run_header(rows, freeze_sha, freeze)
    v4.validate_case_sequence(rows, cases)
    v4.validate_chunk_boundaries(rows, cases, freeze, freeze_sha)
    expected_attempts = {'case-000-attempt-0', 'case-000-attempt-1'} | {
        f'case-{index:03d}-attempt-0' for index in range(1, 7)}
    first.must(all((run / 'attempts' / name).is_dir() and
                   not (run / 'attempts' / name).is_symlink()
                   for name in expected_attempts),
               'one of the seven journaled attempt directories is missing')
    retry = first.check_preconfig_retry(
        root, run, rows, cases[0], freeze_sha)
    receipts = []
    for index in range(COMPLETED_COUNT):
        attempt = 1 if index == 0 else 0
        check_process_receipts(run, rows, index, attempt)
        receipts.append(first.check_successful_case(
            run, rows, index, attempt, cases[index],
            old['runtime_fingerprint_sha256']))
    first.must([r['calibration_sha256'] for r in boundaries['completed']] ==
               receipts,
               'seven independently replayed calibrations differ from journal')
    return {
        'schema': SCHEMA,
        'date': '2026-09-29',
        'status': 'seven_v4_evaluator_controls_independently_audited_no_final_admissions',
        'independent_auditor_source_sha256': first.sha(Path(__file__).read_bytes()),
        'shared_two_case_auditor_source_sha256': first.sha(Path(first.__file__).read_bytes()),
        'source_freeze_sha256': freeze_sha,
        'source_commit': freeze['source_commit'],
        'plan_sha256': freeze['plan_sha256'],
        'ordered_task_identity_sha256': freeze['ordered_task_identity_sha256'],
        'preconfig_amendment_freeze_sha256': retry['supplement_sha256'],
        'preconfig_cleanup_receipt_sha256': retry['reconciliation_sha256'],
        'seven_case_journal_prefix_sha256': first.sha(prefix_raw),
        'first_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][0])),
        'second_chunk_receipt_sha256': first.sha(first.canonical(boundaries['chunks'][1])),
        'completed_calibration_receipts_sha256': boundaries['chunks'][1][
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
        'invalid_attempts_by_classification': {retry['classification']: 1},
        'live_disposable_pair_absence_checked': False,
        'historical_v2_v3_controls_reused': 0,
        'model_calls': 0,
        'official_final_admitted': 0,
    }


PUBLIC_FIELDS = {
    'schema', 'date', 'status', 'independent_auditor_source_sha256',
    'shared_two_case_auditor_source_sha256',
    'source_freeze_sha256', 'source_commit', 'plan_sha256',
    'ordered_task_identity_sha256', 'preconfig_amendment_freeze_sha256',
    'preconfig_cleanup_receipt_sha256', 'seven_case_journal_prefix_sha256',
    'first_chunk_receipt_sha256', 'second_chunk_receipt_sha256',
    'completed_calibration_receipts_sha256',
    'planned_distinct_candidate_controls', 'completed_distinct_candidate_controls',
    'positive_saved_state_pass', 'wrong_variant_saved_state_rejected',
    'fresh_clone_material_reset_pass', 'successful_step_process_receipts_reopened',
    'pair_cleanup_verified_events', 'failed_preconfig_infrastructure_attempts',
    'reconciled_same_id_infrastructure_retries', 'invalid_attempts_by_classification',
    'live_disposable_pair_absence_checked', 'historical_v2_v3_controls_reused',
    'model_calls', 'official_final_admitted',
}


def render_markdown(report: dict) -> str:
    first.must(set(report) == PUBLIC_FIELDS, 'unexpected public report fields')
    return (
        '# Magento v4: independent audit of the first seven controls\n\n'
        'The first two complete bounded chunks contain **7 of 100** planned, '
        'ordered original-Magento evaluator GUI controls. All seven saved-state '
        'positives score 1, wrong-variant controls score 0, and fresh-clone '
        'material resets pass independent replay against retained SQL and '
        'search snapshots. All 91 successful step process receipts and 14 '
        'pair-cleanup journal events were reopened. This is evaluator '
        'calibration only: **0 model calls and 0 official final tasks admitted**.\n\n'
        'The first case had one before-seed, before-GUI HTTP startup failure. '
        'Its exact disposable pair was retired under a source-frozen '
        'reconciliation receipt, followed by one same-ID retry. The seven-case '
        'journal prefix and both bounded chunk receipts are hash-bound in the '
        'adjacent JSON. Later journal appends do not change this prefix. Live '
        'container absence was not rechecked for this read-only audit while '
        'another workload used the same Docker context.\n\n'
        'Historical v2/v3 controls contribute zero. The remaining 93 controls, '
        'per-task final admission, researcher campaigns, and model final '
        'outcomes are not established here. Raw task and saved-state files stay '
        'in private evaluator storage for authorized replay.\n'
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
    report = audit_seven(args.repo_root, args.run_dir)
    first.must(set(report) == PUBLIC_FIELDS, 'public output field allowlist changed')
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
