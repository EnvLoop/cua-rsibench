"""Predeclared paired and source-family summaries for admitted final outcomes.

Only complete, valid, binary outcomes on the same 100 frozen identities enter
these calculations. Infrastructure-invalid attempts must be reconciled before
calling this module; they are never silently mapped to zero. Intervals describe
task/source-family variation conditional on one checkpoint and rollout seed,
not variation across independent training runs.
"""

from __future__ import annotations

from collections import defaultdict
import math
import random


EXPECTED_TASKS = 100
DEFAULT_REPLICATES = 10_000


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _binary_scores(value: object, name: str) -> dict[str, int]:
    _require(isinstance(value, dict) and len(value) == EXPECTED_TASKS,
             f'{name}: exactly 100 task outcomes required')
    for task, score in value.items():
        _require(isinstance(task, str) and task.strip() == task and task and
                 type(score) is int and score in (0, 1),
                 f'{name}: invalid task identity or nonbinary score')
    return value


def _percentile(sorted_values: list[float], fraction: float) -> float:
    position = fraction * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return (sorted_values[lower] * (upper - position) +
            sorted_values[upper] * (position - lower)) if lower != upper else sorted_values[lower]


def _interval(values: list[float]) -> list[float]:
    values.sort()
    return [_percentile(values, 0.025), _percentile(values, 0.975)]


def paired_summary(base: object, selected: object, source_family: object,
                   *, seed: int = 23, replicates: int = DEFAULT_REPLICATES) -> dict:
    base = _binary_scores(base, 'base')
    selected = _binary_scores(selected, 'selected')
    _require(set(base) == set(selected), 'base/selected task identities differ')
    _require(isinstance(source_family, dict) and set(source_family) == set(base) and
             all(isinstance(family, str) and family.strip() == family and family
                 for family in source_family.values()),
             'source family missing or invalid')
    _require(type(seed) is int and 0 <= seed < 2**31 and
             type(replicates) is int and 100 <= replicates <= 100_000,
             'bootstrap seed or replicate count invalid')
    task_ids = sorted(base)
    differences = [selected[task] - base[task] for task in task_ids]
    families: dict[str, list[int]] = defaultdict(list)
    family_base: dict[str, int] = defaultdict(int)
    family_selected: dict[str, int] = defaultdict(int)
    for task in task_ids:
        family = source_family[task]
        families[family].append(selected[task] - base[task])
        family_base[family] += base[task]
        family_selected[family] += selected[task]
    family_names = sorted(families)
    family_rows = [{
        'source_family': family,
        'task_count': len(families[family]),
        'base_wins': family_base[family],
        'selected_wins': family_selected[family],
        'improved_tasks': sum(value == 1 for value in families[family]),
        'regressed_tasks': sum(value == -1 for value in families[family]),
        'paired_delta_pp': 100 * sum(families[family]) / len(families[family]),
    } for family in family_names]
    rng = random.Random(seed)
    task_draws = []
    cluster_draws = []
    for _ in range(replicates):
        task_draws.append(100 * sum(rng.choice(differences)
                                    for _ in range(EXPECTED_TASKS)) / EXPECTED_TASKS)
        if len(family_names) >= 2:
            sampled = [rng.choice(family_names) for _ in family_names]
            total = sum(sum(families[family]) for family in sampled)
            count = sum(len(families[family]) for family in sampled)
            cluster_draws.append(100 * total / count)
    return {
        'schema': 'cua-full-study-paired-summary-v1',
        'task_count': EXPECTED_TASKS,
        'source_family_count': len(family_names),
        'base_wins': sum(base.values()),
        'selected_wins': sum(selected.values()),
        'base_success_percent': 100 * sum(base.values()) / EXPECTED_TASKS,
        'selected_success_percent': 100 * sum(selected.values()) / EXPECTED_TASKS,
        'paired_delta_pp': 100 * sum(differences) / EXPECTED_TASKS,
        'improved_tasks': sum(value == 1 for value in differences),
        'regressed_tasks': sum(value == -1 for value in differences),
        'unchanged_tasks': sum(value == 0 for value in differences),
        'source_family_outcomes': family_rows,
        'primary_family_cluster_interval_pp': _interval(cluster_draws) if cluster_draws else None,
        'family_interval_interpretation': (
            'cluster_resampled_conditional_on_one_checkpoint_and_rollout'
            if len(family_names) >= 10 else
            'descriptive_fewer_than_ten_families'),
        'secondary_task_bootstrap_interval_pp': _interval(task_draws),
        'bootstrap_seed': seed, 'bootstrap_replicates': replicates,
        'single_rollout_stability_unknown': True,
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    """Step-down adjusted p-values; the official study supplies 24 values."""
    _require(isinstance(p_values, list) and p_values and
             all(type(value) in (int, float) and math.isfinite(value) and
                 0 <= value <= 1 for value in p_values),
             'finite p-values from zero to one required')
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(ordered)
    running = 0.0
    for rank, (index, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - rank) * value))
        adjusted[index] = running
    return adjusted
