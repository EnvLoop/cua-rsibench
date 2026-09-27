"""Continue one stopped Magento control after a clock-only reset mismatch.

This consumes the existing untouched negative clone. It retains the original
failed exact-reset process, runs the revised saved-state reset audit, then the
planned wrong-variant GUI negative once. It never retries the prior positive,
dispatches a model, or promotes a candidate to an official final task.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from magento_catalog_factory.verify import (
    check_material_reset, read_snapshot,
)
from tools.sweep_magento_original_gui_controls_v1 import (
    APP, SEARCH, TIMEOUT, append_event, assert_absent, cleanup_pair,
    run_step, sha, write_new,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sweep-dir', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    sweep, plan, source = (path.resolve() for path in
                           (args.sweep_dir, args.plan, args.source))
    require(all(path.is_relative_to(private) for path in
                (sweep, plan, source)) and
            sha(plan.read_bytes()) == args.plan_sha256,
            'private stopped sweep, source and pinned plan required')
    journal = sweep / 'events.private.jsonl'
    old_raw = journal.read_bytes()
    events = [json.loads(line) for line in old_raw.splitlines()]
    require(events and events[-1]['event'] == 'sweep_stopped' and
            events[-1]['requested'] == 1 and
            any(row.get('event') == 'step_finished' and
                row.get('index') == args.index and
                row.get('step') == 'fresh-reset' and
                row.get('exit_code') != 0 for row in events) and
            any(row.get('event') == 'pair_cleanup_verified' and
                row.get('index') == args.index and
                row.get('pair') == 'positive' for row in events) and
            not any(row.get('index') == args.index and
                    row.get('step') == 'negative-gui' for row in events),
            'not an isolated stopped clock-only reset control')
    manifest = json.loads(plan.read_bytes())
    case_row = manifest['cases']['official_candidate'][args.index]
    case = load_case(plan, args.plan_sha256, case_row['task_id'])
    case_dir = sweep / f'case-{args.index:03d}'
    pos, neg = case_dir / 'positive', case_dir / 'negative'
    before = [json.loads((path / 'normalized-baseline.private.json').read_bytes())
              for path in (pos, neg)]
    reset_exception = check_material_reset(*before)
    require(reset_exception == ['target_stock_low_stock_date_clock'] and
            json.loads((pos / 'gui-positive/result.json').read_bytes())[
                'score']['score'] == 1.0 and
            not (neg / 'gui-wrong-variant').exists() and
            not (case_dir / 'calibration.private.json').exists(),
            'saved positive or clock-only negative clone binding changed')
    seed = json.loads((neg / 'seed.private.json').read_bytes())
    runtime = neg / 'runtime.private.json'
    lock = ROOT / 'work/magento-original/exclusive-worker.lock'
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        live = read_snapshot(case, APP, 7794, 7795, seed['page_id'],
                             search_host=SEARCH)
        live_exception = check_material_reset(before[1], live)
        require(not (set(live_exception) - set(reset_exception)),
                'live negative clone changed materially before recovery')
        append_event(journal, {
            'event': 'operator_resume_clock_only_reset',
            'index': args.index, 'time': time.time(),
            'stopped_journal_sha256': sha(old_raw),
            'reset_allowed_volatile_fields': reset_exception,
            'live_allowed_volatile_fields': live_exception,
            'model_calls': 0, 'official_final_admitted': 0,
        })
        required = [str(sys.executable), '--plan', str(plan),
                    '--plan-sha256', args.plan_sha256,
                    '--task-id', case['task_id']]
        reset_out = neg / 'fresh-reset-clock-reconciled.private.json'
        run_step(neg, journal, args.index, 'fresh-reset-clock-reconciled',
                 [str(sys.executable), str(ROOT / 'tools/audit_magento_original_fresh_reset_v1.py'),
                  *required[1:],
                  '--first-before', str(pos / 'normalized-baseline.private.json'),
                  '--second-before', str(neg / 'normalized-baseline.private.json'),
                  '--first-seed', str(pos / 'seed.private.json'),
                  '--second-seed', str(neg / 'seed.private.json'),
                  '--first-runtime', str(pos / 'runtime.private.json'),
                  '--second-runtime', str(runtime),
                  '--first-finalization', str(pos / 'finalization.private.json'),
                  '--second-finalization', str(neg / 'finalization.private.json'),
                  '--out', str(reset_out)], timeout=TIMEOUT['reset'])
        reset = json.loads(reset_out.read_bytes())
        require(reset['fresh_clone_reset_passed'] is True and
                reset['exact_monitored_sql_and_search_state'] is False and
                reset['allowed_volatile_fields'] == reset_exception,
                'clock-only reset audit changed')
        control = neg / 'gui-wrong-variant'
        result = run_step(neg, journal, args.index, 'negative-gui',
                          [str(sys.executable), str(ROOT / 'tools/qualify_magento_original_catalog_v1.py'),
                           *required[1:], '--source', str(source),
                           '--container', APP, '--http-port', '7794',
                           '--control-port', '7795',
                           '--page-id', str(seed['page_id']),
                           '--search-host', SEARCH,
                           '--mode', 'wrong-variant', '--out', str(control)],
                          timeout=TIMEOUT['wrong_variant'])
        require(result['score'] == 0.0,
                'planned wrong-variant GUI control did not fail')
        cleanup_pair(runtime)
        assert_absent()
        append_event(journal, {'event': 'pair_cleanup_verified',
                               'index': args.index, 'pair': 'negative',
                               'time': time.time()})
        inputs = {'positive_' + key: sha((pos / name).read_bytes())
                  for key, name in (
                      ('seed', 'seed.private.json'),
                      ('baseline', 'normalized-baseline.private.json'),
                      ('runtime', 'runtime.private.json'),
                      ('finalization', 'finalization.private.json'))}
        inputs.update({'negative_' + key: sha((neg / name).read_bytes())
                       for key, name in (
                           ('seed', 'seed.private.json'),
                           ('baseline', 'normalized-baseline.private.json'),
                           ('runtime', 'runtime.private.json'),
                           ('finalization', 'finalization.private.json'))})
        summary = {
            'schema': 'envloop-magento-original-gui-case-calibration-v1',
            'task_id': case['task_id'],
            'package_sha256': case['package_sha256'],
            'split': case['split'], 'policy_kind': case['policy_kind'],
            'positive_score': 1.0, 'wrong_variant_score': 0.0,
            'fresh_reset_passed': True,
            'fresh_reset_exact': False,
            'reset_allowed_volatile_fields': reset_exception,
            'stopped_journal_sha256': sha(old_raw),
            'reset_recovery_receipt_sha256': sha(reset_out.read_bytes()),
            'model_calls': 0, 'official_final_admitted': False,
            'receipt_sha256': inputs,
        }
        digest = write_new(case_dir / 'calibration.private.json', summary)
        append_event(journal, {'event': 'task_gui_calibrated',
                               'index': args.index, 'task_id': case['task_id'],
                               'receipt_sha256': digest, 'time': time.time(),
                               'reset_clock_reconciled': True,
                               'official_final_admitted': 0})
        append_event(journal, {'event': 'sweep_completed_after_reconciliation',
                               'passed': 1, 'requested': 1,
                               'time': time.time(),
                               'official_final_admitted': 0})
        print(json.dumps({'status': 'candidate_gui_calibrated_after_clock_audit',
                          'case_receipt_sha256': digest,
                          'reset_allowed_volatile_fields': reset_exception,
                          'official_final_admitted': 0}, sort_keys=True))
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


if __name__ == '__main__':
    main()
