"""Publish field-limited original Magento GUI candidate-control progress."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import load_case


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--through-index', type=int, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    plan = args.plan.resolve()
    require(plan.is_relative_to(private) and
            sha(plan.read_bytes()) == args.plan_sha256 and
            0 <= args.through_index < 100 and
            not args.public_out.exists(),
            'pinned plan and fresh public receipt required')
    manifest = json.loads(plan.read_bytes())
    cases = manifest['cases']['official_candidate']
    require(len(cases) == 100, 'original Magento 100-case manifest changed')
    roots = list((private / 'magento-original').glob('sweep-final-*'))
    bound = []
    clock_exception = 0
    for index in range(args.through_index + 1):
        case = load_case(plan, args.plan_sha256, cases[index]['task_id'])
        found = [root / f'case-{index:03d}/calibration.private.json'
                 for root in roots
                 if (root / f'case-{index:03d}/calibration.private.json').is_file()]
        require(len(found) == 1, 'zero or duplicate calibration at selected index')
        receipt = found[0]
        raw = receipt.read_bytes()
        value = json.loads(raw)
        require(value['schema'] ==
                'envloop-magento-original-gui-case-calibration-v1' and
                value['task_id'] == case['task_id'] and
                value['package_sha256'] == case['package_sha256'] and
                value['split'] == 'official_candidate' and
                value['positive_score'] == 1.0 and
                value['wrong_variant_score'] == 0.0 and
                value['fresh_reset_passed'] is True and
                value['model_calls'] == 0 and
                value['official_final_admitted'] is False,
                'case evidence is incomplete or claims a model result')
        root = receipt.parent.parent
        journal = root / 'events.private.jsonl'
        events = [json.loads(line) for line in journal.read_bytes().splitlines()]
        require(any(row.get('event') == 'task_gui_calibrated' and
                    row.get('index') == index and
                    row.get('task_id') == case['task_id'] and
                    row.get('receipt_sha256') == sha(raw) for row in events) and
                all(any(row.get('event') == 'pair_cleanup_verified' and
                        row.get('index') == index and row.get('pair') == pair
                        for row in events) for pair in ('positive', 'negative')),
                'GUI/cleanup journal does not bind case receipt')
        for pair, expected in (('positive', 1.0), ('negative', 0.0)):
            filename = ('gui-positive' if pair == 'positive' else
                        'gui-wrong-variant')
            result = json.loads((receipt.parent / pair / filename /
                                 'result.json').read_bytes())
            require(result['score']['score'] == expected and
                    result['official_final_tasks_admitted'] == 0,
                    'independent saved-state GUI score changed')
        allowed = value.get('reset_allowed_volatile_fields', [])
        require(allowed in ([], ['target_stock_low_stock_date_clock']),
                'unregistered reset exception')
        clock_exception += bool(allowed)
        bound.append(sha(raw))
    public = {
        'schema': 'envloop-magento-original-gui-progress-public-v1',
        'status': 'gui_candidate_controls_not_official_final_admission',
        'distinct_final_candidate_ids_gui_calibrated': len(bound),
        'total_final_candidate_ids': 100,
        'positive_saved_state_pass': len(bound),
        'wrong_variant_saved_state_rejected': len(bound),
        'fresh_clone_material_reset_pass': len(bound),
        'reset_clock_only_exception_count': clock_exception,
        'receipt_list_sha256': sha(('\n'.join(bound) + '\n').encode()),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    raw = (json.dumps(public, indent=2, sort_keys=True) + '\n').encode()
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': public['status'],
                      'public_sha256': sha(raw),
                      'gui_calibrated': len(bound),
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
