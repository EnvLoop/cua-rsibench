"""Publish aggregate-only PowerPoint split and difficulty-shape evidence."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from tools.prepare_ppt_wdi_web_final_gui_v1 import SLIDES


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    plan_path = args.private_plan.resolve()
    require(plan_path.is_relative_to(private) and not args.out.exists(),
            'private plan and fresh public output required')
    raw = plan_path.read_bytes()
    require(sha(raw) == args.plan_sha256, 'frozen private plan changed')
    plan = json.loads(raw)
    require(plan['revision'] == 'private_wdi_seven_reserves_and_web_chart_v9',
            'current pre-result PowerPoint source pool required')
    sets = plan['sets']
    require({key: len(rows) for key, rows in sets.items()} ==
            {'train': 20, 'selection': 20, 'final_candidate': 100},
            'split counts changed')
    groups = {split: {row['source_group'] for row in rows}
              for split, rows in sets.items()}
    ids = {split: {row['task_id'] for row in rows}
           for split, rows in sets.items()}
    instances = {split: {row['instance_group'] for row in rows}
                 for split, rows in sets.items()}
    workflows = {split: {row['workflow'] for row in rows}
                 for split, rows in sets.items()}
    splits = ('train', 'selection', 'final_candidate')
    for index, left in enumerate(splits):
        require(len(ids[left]) == len(sets[left]) and
                len(instances[left]) == len(sets[left]),
                f'{left}: repeated identity or instance')
        for right in splits[index + 1:]:
            require(not (groups[left] & groups[right] or
                         ids[left] & ids[right] or
                         instances[left] & instances[right]),
                    'source/task/instance overlap between splits')
    expected_targets = {'train': 1, 'selection': 3,
                        'final_candidate': 4}
    for split, rows in sets.items():
        require(all(len(row['target_keys']) == expected_targets[split]
                    and len(set(row['target_keys'])) ==
                    expected_targets[split] for row in rows),
                f'{split}: target dependency count changed')
    finals = sets['final_candidate']
    workflow_counts = Counter(row['workflow'] for row in finals)
    family_counts = Counter(row['source_group'] for row in finals)
    require(len(workflow_counts) == 10 and
            set(workflow_counts.values()) == {10} and
            len(family_counts) == 25 and
            set(family_counts.values()) == {4} and
            all(len({SLIDES[key] for key in row['target_keys']}) == 4
                for row in finals),
            'ten balanced workflows, 25 families and four slides required')
    result = {
        'schema': 'envloop-ppt-wdi-split-difficulty-shape-public-v1',
        'status': 'offline_structure_not_user_or_model_difficulty_measure',
        'private_plan_sha256': sha(raw),
        'split_candidate_counts': {key: len(rows) for key, rows in sets.items()},
        'independent_source_families_by_split':
            {key: len(value) for key, value in groups.items()},
        'task_and_instance_ids_disjoint_across_splits': True,
        'source_families_disjoint_across_splits': True,
        'target_fields_per_task': expected_targets,
        'final_target_fields_on_distinct_slides': True,
        'final_source_families': len(family_counts),
        'final_tasks_per_source_family': 4,
        'final_causal_workflow_types': len(workflow_counts),
        'final_tasks_per_workflow_type': 10,
        'causal_workflow_types_shared_train_and_final':
            len(workflows['train'] & workflows['final_candidate']),
        'causal_workflow_types_shared_selection_and_final':
            len(workflows['selection'] & workflows['final_candidate']),
        'final_causal_workflow_types_unseen_in_selection':
            len(workflows['final_candidate'] - workflows['selection']),
        'no_unseen_workflow_generalization_claim': True,
        'official_final_admitted': 0,
        'model_calls': 0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    output = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(output)
    print(json.dumps({'status': result['status'],
                      'source_families': result['final_source_families'],
                      'final_workflows': result['final_causal_workflow_types'],
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
