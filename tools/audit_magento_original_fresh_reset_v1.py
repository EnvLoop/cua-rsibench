"""Prove exact observed state after reseeding one task in a different fresh clone.

The two snapshots must be captured before actor actions. This checks the
reset baseline; it does not itself run a GUI positive/negative or admit a task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import IMAGE, load_case
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_HOST, NATIVE_SEARCH_IMAGE, NATIVE_SEARCH_NETWORK,
)
from magento_catalog_factory.verify import check_baseline, check_exact_reset


def read_private(path: Path) -> tuple[dict, str]:
    path = path.resolve()
    require(path.is_relative_to((ROOT / 'work').resolve()) and path.is_file(),
            'private evidence under ignored work/ required')
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def snapshot_sha256(value: dict) -> str:
    return hashlib.sha256((json.dumps(value, sort_keys=True, indent=2) + '\n').encode()).hexdigest()


def audit(case: dict, first: dict, second: dict,
          first_seed: dict, second_seed: dict,
          first_runtime: dict, second_runtime: dict,
          first_finalization: dict, second_finalization: dict) -> dict:
    check_baseline(case, first)
    check_baseline(case, second)
    for receipt in (first_seed, second_seed):
        require(receipt['status'] == 'trusted_fixture_seeded_not_gui_admitted' and
                receipt['task_id'] == case['task_id'] and
                receipt['package_sha256'] == case['package_sha256'] and
                receipt['quote_page_body_sha256'] == case['quote_page_body_sha256'] and
                receipt['clone']['image_sha256'] == IMAGE and
                receipt['clone']['mount_count'] == 0,
                'trusted task seed/clone binding changed')
    require(first_seed['clone']['container_id_sha256'] !=
            second_seed['clone']['container_id_sha256'],
            'reset used the same container identity')
    require(first_seed['clone']['loopback_ports'] ==
            second_seed['clone']['loopback_ports'],
            'fresh attempt changed the benchmark URL/port')
    require(first['page_id'] == first_seed['page_id'] and
            second['page_id'] == second_seed['page_id'],
            'snapshot and trusted seed page differ')
    for state, seed, runtime, finalization in (
            (first, first_seed, first_runtime, first_finalization),
            (second, second_seed, second_runtime, second_finalization)):
        require(runtime['schema'] ==
                'envloop-magento-native-sidecar-runtime-private-v1' and
                runtime['app'] == seed['clone'] and
                runtime['sidecar_image_sha256'] == NATIVE_SEARCH_IMAGE and
                runtime['network'] == NATIVE_SEARCH_NETWORK and
                runtime['baseline_sha256'] == snapshot_sha256(state) and
                finalization['status'] == 'normalized_baseline_frozen_not_gui_admitted' and
                finalization['task_id'] == case['task_id'] and
                finalization['package_sha256'] == case['package_sha256'] and
                finalization['clone'] == seed['clone'] and
                finalization['search_backend'] == NATIVE_SEARCH_HOST and
                finalization['normalized_baseline_sha256'] == snapshot_sha256(state),
                'same-topology normalized runtime binding changed')
    require(first_runtime['sidecar_id_sha256'] !=
            second_runtime['sidecar_id_sha256'],
            'fresh reset reused the same search container')
    check_exact_reset(first, second)
    return {'schema': 'envloop-magento-original-fresh-reset-v1',
            'task_id': case['task_id'], 'package_sha256': case['package_sha256'],
            'fresh_clone_reset_passed': True,
            'different_container_ids': True,
            'different_search_container_ids': True,
            'same_pinned_application_and_search_images': True,
            'exact_monitored_sql_and_search_state': True,
            'official_final_tasks_admitted': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--first-before', type=Path, required=True)
    parser.add_argument('--second-before', type=Path, required=True)
    parser.add_argument('--first-seed', type=Path, required=True)
    parser.add_argument('--second-seed', type=Path, required=True)
    parser.add_argument('--first-runtime', type=Path, required=True)
    parser.add_argument('--second-runtime', type=Path, required=True)
    parser.add_argument('--first-finalization', type=Path, required=True)
    parser.add_argument('--second-finalization', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new private reset receipt under work/ required')
    case = load_case(args.plan, args.plan_sha256, args.task_id)
    values = [read_private(path) for path in
              (args.first_before, args.second_before,
               args.first_seed, args.second_seed,
               args.first_runtime, args.second_runtime,
               args.first_finalization, args.second_finalization)]
    result = audit(case, *(row[0] for row in values))
    result['input_sha256'] = {name: value[1] for name, value in zip(
        ('first_before', 'second_before', 'first_seed', 'second_seed',
         'first_runtime', 'second_runtime',
         'first_finalization', 'second_finalization'), values)}
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    with out.open('xb') as stream:
        stream.write(raw)
    out.chmod(0o600)
    print(json.dumps({'fresh_clone_reset_passed': True,
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
