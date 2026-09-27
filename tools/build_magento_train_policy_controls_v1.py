"""Create four private five-variant policy controls on train-only parents.

These examples reuse training source families, never selection or final parent
families. They exercise the four five-variant policies before private per-ID
final admission, without exposing any held-out identity or answer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from magento_catalog_factory import plan as factory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--candidate-plan', type=Path, required=True)
    parser.add_argument('--candidate-plan-sha256', required=True)
    parser.add_argument('--seed-file', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (factory.ROOT / 'work').resolve()
    paths = [args.inventory.resolve(), args.candidate_plan.resolve(),
             args.seed_file.resolve(), args.out.resolve()]
    factory.require(all(path.is_relative_to(private) for path in paths) and
                    not paths[-1].exists(), 'ignored private inputs/new output required')
    raw_inventory = paths[0].read_bytes()
    inventory = json.loads(raw_inventory)
    factory.require(hashlib.sha256(raw_inventory).hexdigest() ==
                    factory.INVENTORY_SHA256,
                    'source catalog inventory changed')
    raw_plan = paths[1].read_bytes()
    factory.require(hashlib.sha256(raw_plan).hexdigest() ==
                    args.candidate_plan_sha256,
                    'original 20/20/100 plan changed')
    original = json.loads(raw_plan)
    factory.require(original['split_counts'] == factory.SPLITS and
                    original['official_final_admitted_count'] == 0,
                    'original candidate split changed')
    train_parents = {case['parent_id'] for case in original['cases']['train']}
    held_out = {case['parent_id'] for split in ('selection', 'official_candidate')
                for case in original['cases'][split]}
    factory.require(train_parents.isdisjoint(held_out),
                    'train source family leaked into held-out set')
    seed = paths[2].read_text().strip()
    train_sources = sorted((row for row in inventory['parents']
                            if row['parent_id'] in train_parents and
                            len(row['children']) >= 7),
                     key=lambda row: factory.digest({'seed': seed,
                                                     'train_policy': row['parent_sku']}))[:4]
    factory.require(len(train_sources) == 4 and
                    len({row['parent_id'] for row in train_sources}) == 4,
                    'four disjoint seven-variant train parents required')
    cases = [factory._case(seed, parent, 'train_policy_development', ordinal)
             for ordinal, parent in enumerate(train_sources)]
    document = {'schema': factory.SCHEMA,
                'status': 'offline_candidates_not_gui_admitted',
                'source_inventory_sha256': factory.INVENTORY_SHA256,
                'original_candidate_plan_sha256': args.candidate_plan_sha256,
                'cases': {'train_policy_development': cases},
                'official_final_admitted_count': 0,
                'model_scores_present': False}
    paths[-1].parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(paths[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': 'private_train_policy_development_not_final',
                      'count': 4,
                      'policy_count': len({row['policy_kind'] for row in cases}),
                      'private_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
