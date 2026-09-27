"""Audit one Magento infrastructure retry without erasing its failed source."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from tools.sweep_magento_original_gui_controls_v1 import APP, SEARCH, sha


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--original-sweep', type=Path, required=True)
    parser.add_argument('--retry-sweep', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    plan, original, retry = (path.resolve() for path in
                             (args.plan, args.original_sweep, args.retry_sweep))
    require(all(path.is_relative_to(private) for path in
                (plan, original, retry)) and
            not args.out.exists() and
            sha(plan.read_bytes()) == args.plan_sha256 and
            0 <= args.index < 100,
            'private pinned source, stopped/retry journals and fresh output required')
    candidate = json.loads(plan.read_bytes())['cases']['official_candidate'][args.index]
    case = load_case(plan, args.plan_sha256, candidate['task_id'])
    original_raw = (original / 'events.private.jsonl').read_bytes()
    retry_raw = (retry / 'events.private.jsonl').read_bytes()
    first = [json.loads(line) for line in original_raw.splitlines()]
    second = [json.loads(line) for line in retry_raw.splitlines()]
    require(first[-1]['event'] ==
            'operator_reconciled_negative_neutral_ui_unstable' and
            first[-1]['index'] == args.index and
            any(row.get('event') == 'step_finished' and
                row.get('index') == args.index and
                row.get('step') == 'negative-neutral' and
                row.get('exit_code') != 0 for row in first) and
            second[0]['event'] == 'sweep_started' and
            second[0]['recovery_of_private_journal_sha256'] == sha(original_raw) and
            second[0]['recovery_kind'] ==
            'postpositive_negative_neutral_ui_unstable' and
            second[0]['start_index'] == args.index and
            second[0]['limit'] == 1 and
            second[-1]['event'] == 'sweep_completed' and
            second[-1]['passed'] == second[-1]['requested'] == 1 and
            all(row.get('exit_code') == 0 for row in second
                if row.get('event') == 'step_finished'),
            'original failure or single complete retry changed')
    receipt_path = retry / f'case-{args.index:03d}/calibration.private.json'
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    require(receipt['task_id'] == case['task_id'] and
            receipt['package_sha256'] == case['package_sha256'] and
            receipt['positive_score'] == 1.0 and
            receipt['wrong_variant_score'] == 0.0 and
            receipt['fresh_reset_passed'] is True and
            receipt['model_calls'] == 0 and
            receipt['official_final_admitted'] is False and
            any(row.get('event') == 'task_gui_calibrated' and
                row.get('index') == args.index and
                row.get('receipt_sha256') == sha(raw) for row in second) and
            all(any(row.get('event') == 'pair_cleanup_verified' and
                    row.get('index') == args.index and
                    row.get('pair') == pair for row in second)
                for pair in ('positive', 'negative')) and
            not (original / f'case-{args.index:03d}/calibration.private.json').exists(),
            'fresh retry score/reset/cleanup or original failure changed')
    recovery_starts = 0
    for journal in private.glob('magento-original/sweep-*/events.private.jsonl'):
        rows = journal.read_bytes().splitlines()
        if rows and json.loads(rows[0]).get('recovery_of_private_journal_sha256') == sha(original_raw):
            recovery_starts += 1
    require(recovery_starts == 1, 'more than one recovery dispatched')
    for name in (APP, SEARCH):
        probe = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                'inspect', name], capture_output=True,
                               timeout=20)
        require(probe.returncode != 0,
                'retry disposable Magento container not cleaned')
    public = {
        'schema': 'envloop-magento-negative-neutral-retry-public-v1',
        'status': 'one_bounded_fresh_clone_gui_retry_passed_development_only',
        'original_reconciled_journal_private_sha256': sha(original_raw),
        'retry_journal_private_sha256': sha(retry_raw),
        'retry_calibration_private_sha256': sha(raw),
        'original_failed_attempts_retained': 1,
        'fresh_full_task_retries_dispatched': 1,
        'fresh_full_task_retries_allowed': 1,
        'retry_positive_score': 1,
        'retry_wrong_variant_score': 0,
        'retry_fresh_clone_material_reset': True,
        'retry_app_search_pairs_cleaned': 2,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
    output = (json.dumps(public, indent=2, sort_keys=True) + '\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(output)
    print(json.dumps({'status': public['status'],
                      'receipt_sha256': hashlib.sha256(output).hexdigest(),
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
