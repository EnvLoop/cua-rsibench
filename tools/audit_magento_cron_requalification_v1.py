"""Audit all 100 fresh GUI controls under one frozen Magento cron policy.

Only a complete 0..99 sweep yields an aggregate. This is a calibration audit,
not an official final-task admission or a model outcome.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case
from tools import magento_cron_runtime_contract_v1 as contract
from tools.freeze_magento_cron_runtime_v1 import PROBE_DIR, TRAIN_DIR


def audit(plan: Path, plan_sha256: str, sweep: Path, freeze: Path) -> dict:
    frozen, freeze_sha = contract.validate_freeze(freeze, ROOT, PROBE_DIR, TRAIN_DIR)
    require(contract.sha(plan.read_bytes()) == plan_sha256 ==
            frozen['final_candidate_plan_sha256'],
            '100-task plan differs from the frozen training plan')
    cases = json.loads(plan.read_bytes())['cases']['official_candidate']
    require(len(cases) == 100 and
            len({case['task_id'] for case in cases}) == 100 and
            len({case['package_sha256'] for case in cases}) == 100,
            'exactly 100 distinct original task packages required')
    journal_raw = (sweep / 'events.private.jsonl').read_bytes()
    events = [json.loads(line) for line in journal_raw.splitlines()]
    require(bool(events) and events[0].get('event') == 'sweep_started' and
            events[0].get('split') == 'official_candidate' and
            events[0].get('start_index') == 0 and events[0].get('limit') == 100 and
            events[0].get('plan_sha256') == plan_sha256 and
            events[0].get('cellwide_cron_freeze_sha256') == freeze_sha and
            events[0].get('runtime_fingerprint_sha256') ==
            frozen['runtime_fingerprint_sha256'] and
            events[0].get('recovery_of_private_journal_sha256') is None and
            events[0].get('model_calls') == 0 and
            events[0].get('official_final_admitted') is False and
            events[-1].get('event') == 'sweep_completed' and
            events[-1].get('passed') == events[-1].get('requested') == 100 and
            events[-1].get('official_final_admitted') == 0 and
            not any(row.get('event') in ('sweep_stopped', 'step_timeout_uncertain')
                    for row in events),
            'one uninterrupted, non-scoring fresh 100-case sweep required')
    completed = [row for row in events if row.get('event') == 'task_gui_calibrated']
    cleanups = [row for row in events if row.get('event') == 'pair_cleanup_verified']
    require([row.get('index') for row in completed] == list(range(100)) and
            [(row.get('index'), row.get('pair')) for row in cleanups] ==
            [(index, pair) for index in range(100)
             for pair in ('positive', 'negative')],
            '100 calibrations and 200 ordered pair cleanups required')
    hashes = []
    clock_exceptions = 0
    for index, original in enumerate(cases):
        case = load_case(plan, plan_sha256, original['task_id'])
        case_dir = sweep / f'case-{index:03d}'
        calibration, calibration_sha = contract.read(case_dir / 'calibration.private.json')
        require(completed[index].get('receipt_sha256') == calibration_sha and
                completed[index].get('task_id') == case['task_id'] and
                calibration['schema'] == 'envloop-magento-original-gui-case-calibration-v1' and
                calibration['task_id'] == case['task_id'] and
                calibration['package_sha256'] == case['package_sha256'] and
                calibration['split'] == 'official_candidate' and
                calibration['positive_score'] == 1.0 and
                calibration['wrong_variant_score'] == 0.0 and
                calibration['fresh_reset_passed'] is True and
                calibration['cellwide_cron_runtime_fingerprint_sha256'] ==
                frozen['runtime_fingerprint_sha256'] and
                calibration['model_calls'] == 0 and
                calibration['official_final_admitted'] is False,
                'candidate calibration was not produced by this frozen runtime')
        for pair, mode, score in (('positive', 'gui-positive', 1.0),
                                  ('negative', 'gui-wrong-variant', 0.0)):
            prepared, prep_sha = contract.read(case_dir / pair / 'prepare.private.json')
            contract.validate_prepared(prepared,
                                       config_sha256=frozen['runtime']['cron_config_sha256'])
            require(calibration['receipt_sha256'][f'{pair}_prepare'] == prep_sha,
                    'candidate preparation hash changed')
            result, _ = contract.read(case_dir / pair / mode / 'result.json')
            require(result['score']['score'] == score and
                    result['score']['independent_saved_state'] is True and
                    result['score']['task_id'] == case['task_id'] and
                    result['model_calls'] == result['official_final_tasks_admitted'] == 0,
                    'independent saved-state score changed')
        reset, _ = contract.read(case_dir / 'negative/fresh-reset.private.json')
        require(reset['fresh_clone_reset_passed'] is True and
                reset['material_monitored_sql_and_search_state'] is True and
                reset['different_container_ids'] is True and
                reset['different_search_container_ids'] is True and
                reset['official_final_tasks_admitted'] == 0,
                'fresh reset missing or altered')
        allowed = reset.get('allowed_volatile_fields', [])
        require(allowed in ([], ['target_stock_low_stock_date_clock']),
                'unregistered reset volatility')
        clock_exceptions += bool(allowed)
        hashes.append(calibration_sha)
    return {'schema': 'envloop-magento-cron-runtime-100-gui-controls-public-v1',
            'status': '100_fresh_gui_controls_passed_not_official_final_admission',
            'historical_controls_reused': 0,
            'historical_controls_preserved': 35,
            'historical_preseed_drift_failures_preserved': 2,
            'runtime_fingerprint_sha256': frozen['runtime_fingerprint_sha256'],
            'freeze_receipt_sha256': freeze_sha,
            'sweep_journal_sha256': contract.sha(journal_raw),
            'calibration_receipt_list_sha256': contract.sha(('\n'.join(hashes) + '\n').encode()),
            'distinct_candidate_controls': 100,
            'positive_saved_state_pass': 100,
            'wrong_variant_saved_state_rejected': 100,
            'fresh_clone_material_reset_pass': 100,
            'reset_clock_only_exception_count': clock_exceptions,
            'model_calls': 0, 'official_final_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--sweep-dir', type=Path, required=True)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    plan, sweep, freeze = (path.resolve() for path in
                           (args.plan, args.sweep_dir, args.freeze))
    require(all(path.is_relative_to(private) for path in (plan, sweep, freeze)) and
            args.public_out.resolve().is_relative_to((ROOT / 'docs/evidence').resolve()) and
            not args.public_out.exists(),
            'private inputs and fresh public aggregate path required')
    receipt = audit(plan, args.plan_sha256, sweep, freeze)
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + '\n').encode()
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': receipt['status'],
                      'public_sha256': contract.sha(raw),
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
