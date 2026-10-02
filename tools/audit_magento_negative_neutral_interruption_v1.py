"""Publish an aggregate-only receipt for one reconciled Magento GUI stop."""

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
    parser.add_argument('--sweep-dir', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    plan, sweep = args.plan.resolve(), args.sweep_dir.resolve()
    require(plan.is_relative_to(private) and sweep.is_relative_to(private) and
            not args.out.exists() and
            sha(plan.read_bytes()) == args.plan_sha256 and
            0 <= args.index < 100,
            'private pinned Magento failure and fresh public output required')
    case_row = json.loads(plan.read_bytes())['cases']['official_candidate'][args.index]
    case = load_case(plan, args.plan_sha256, case_row['task_id'])
    journal_raw = (sweep / 'events.private.jsonl').read_bytes()
    events = [json.loads(line) for line in journal_raw.splitlines()]
    last = events[-1]
    negative = sweep / f'case-{args.index:03d}/negative'
    receipt_path = negative / 'recovery-cleanup.private.json'
    receipt_raw = receipt_path.read_bytes()
    receipt = json.loads(receipt_raw)
    intent_raw = (negative / 'recovery-cleanup-intent.private.json').read_bytes()
    intent = json.loads(intent_raw)
    process = json.loads((negative /
                          'negative-neutral-process.private.json').read_bytes())
    stderr_raw = (negative / 'negative-neutral-stderr.private.bin').read_bytes()
    positive = json.loads((sweep / f'case-{args.index:03d}/positive/'
                           'gui-positive/result.json').read_bytes())
    require(last['event'] ==
            'operator_reconciled_negative_neutral_ui_unstable' and
            last['index'] == args.index and
            last['cleanup_receipt_sha256'] == sha(receipt_raw) and
            last['negative_gui_attempted'] is False and
            receipt['schema'] ==
            'envloop-magento-negative-neutral-ui-cleanup-private-v1' and
            receipt['task_id'] == case['task_id'] and
            receipt['plan_sha256'] == args.plan_sha256 and
            receipt['cleanup_intent_sha256'] == sha(intent_raw) and
            receipt['process_stderr_sha256'] == sha(stderr_raw) and
            receipt['material_state_unchanged'] is True and
            receipt['saved_positive_score'] == 1.0 and
            receipt['negative_gui_attempted'] is False and
            receipt['both_containers_cleaned'] is True and
            receipt['model_calls'] == receipt['official_final_admitted'] == 0 and
            intent['stopped_journal_sha256'] ==
            receipt['original_journal_sha256'] and
            intent['process_stderr_sha256'] == sha(stderr_raw) and
            len(intent['containers']) == 2 and
            positive['score']['score'] == 1.0 and
            process['exit_code'] != 0 and
            process['stderr_sha256'] == sha(stderr_raw) and
            not (negative / 'neutral/result.json').exists() and
            not (negative / 'gui-wrong-variant/result.json').exists(),
            'retained stopped GUI/cleanup evidence changed')
    for name in (APP, SEARCH):
        probe = subprocess.run(['docker', '--context', 'colima-cua-scale',
                                'inspect', name], capture_output=True,
                               timeout=20)
        require(probe.returncode != 0,
                'failed disposable Magento container still exists')
    # A recovery must be separately invoked and must not already exist at the
    # time this pre-result policy receipt is published.
    original_sha = sha(journal_raw)
    for candidate in (private / 'magento-original').glob('sweep-*/events.private.jsonl'):
        if candidate.resolve() == (sweep / 'events.private.jsonl').resolve():
            continue
        lines = candidate.read_bytes().splitlines()
        if lines:
            require(json.loads(lines[0]).get('recovery_of_private_journal_sha256')
                    != original_sha,
                    'recovery already dispatched before public rule receipt')
    public = {
        'schema': 'envloop-magento-negative-neutral-interruption-public-v1',
        'status': 'one_evaluator_gui_infrastructure_stop_reconciled_before_retry',
        'original_stopped_journal_private_sha256':
            receipt['original_journal_sha256'],
        'reconciled_journal_private_sha256': original_sha,
        'cleanup_receipt_private_sha256': sha(receipt_raw),
        'failed_step': 'negative_neutral_cms_quote_open',
        'positive_saved_state_score': 1,
        'negative_gui_edit_attempted': False,
        'failed_clone_material_state_unchanged': True,
        'exact_disposable_container_identities_cleaned': 2,
        'fresh_copy_retries_dispatched': 0,
        'maximum_fresh_copy_retries_allowed': 1,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    raw = (json.dumps(public, indent=2, sort_keys=True) + '\n').encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': public['status'],
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
