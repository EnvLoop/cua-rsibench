"""Plan a source-pinned, template-disjoint Magento qualification backlog.

The output is deliberately an offline *candidate* queue. A published task ID,
hard-subset label, or HTTP-event evaluator is never treated as saved-state or
hidden-final admission evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


SOURCE_SHA256 = 'd65275660814663375028e9017e1f929e3c38321041b125795e2713b52243d30'
HARD_SHA256 = '3b0a4df231bb5a0c642215e521c3fa97701a384f52a734dc2db8f617ad0591a7'
SOURCE_COMMIT = '6473f72db5dcefc97b5725b59e734504edc28a21'
SEED = 'envloop-magento-v06-candidate-split-2026-09-24'
QUARANTINED_TEMPLATES = {
    742: 'task 777 supplied an accepted train-only GUI/SFT technical source after a prior clone-dependent HAR false positive; hold the full family out of candidate evaluation',
    240: 'task 538 was a failed validated-action-contract training probe; retain the exposed development template outside candidate splits, but it is not admitted training data',
    275: 'task 486 visually saved in a training probe but failed the unchanged network evaluator; retain this failed-contract development template outside candidate splits, not as accepted training data',
}
TRAIN_RESERVED_TASK_IDS = {777}
EXPOSED_SOURCE_TASK_IDS = {486, 538, 777}
QUARANTINED_TASKS = {
    423: 'published product-save network assertion expects unrelated report-filter fields; requires GUI, HAR, SQL, and reset qualification',
    491: 'published task expects ACTION_NOT_ALLOWED_ERROR, not a saved mutation; reserve for a separately scored policy-denial cohort',
    790: 'published task expects ACTION_NOT_ALLOWED_ERROR, not a saved mutation; reserve for a separately scored policy-denial cohort',
}
TASK_TYPE_ORDER = {'mutate': 0, 'retrieve': 1, 'navigate': 2}
EXPECTED_SET = {'retrieve', 'navigate', 'mutate'}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True).encode('utf-8')


def source_rows(source: Path, hard_ids: Path) -> tuple[list[dict], set[int]]:
    raw, hard_raw = source.read_bytes(), hard_ids.read_bytes()
    if digest(raw) != SOURCE_SHA256 or digest(hard_raw) != HARD_SHA256:
        raise ValueError('source or hard-subset bytes differ from pinned revision')
    full = json.loads(raw)
    hard = json.loads(hard_raw)
    if not isinstance(full, list) or not isinstance(hard, dict):
        raise ValueError('unexpected upstream manifest schema')
    ids = hard.get('task_ids')
    if not isinstance(ids, list) or not all(type(item) is int for item in ids):
        raise ValueError('hard-subset IDs missing')
    rows = [row for row in full if row.get('sites') == ['shopping_admin']]
    if len(rows) != 182 or len({row.get('task_id') for row in rows}) != 182:
        raise ValueError('pinned Magento inventory count or uniqueness changed')
    if len({row.get('intent_template_id') for row in rows}) != 41:
        raise ValueError('pinned Magento template count changed')
    return rows, set(ids)


def evaluation_shape(row: dict) -> dict:
    evaluations = row.get('eval')
    if not isinstance(evaluations, list) or not evaluations or evaluations[0].get('evaluator') != 'AgentResponseEvaluator':
        raise ValueError('unexpected evaluator chain')
    response = evaluations[0].get('expected', {})
    kind = response.get('task_type')
    status = response.get('status')
    if kind not in EXPECTED_SET:
        raise ValueError('unexpected task type')
    if status not in {'SUCCESS', 'NOT_FOUND_ERROR', 'ACTION_NOT_ALLOWED_ERROR'}:
        raise ValueError('unexpected expected response status')
    if (kind == 'navigate' and status != 'SUCCESS') or (kind == 'mutate' and status == 'NOT_FOUND_ERROR'):
        raise ValueError('unexpected task type/status combination')
    network = [item for item in evaluations[1:] if item.get('evaluator') == 'NetworkEventEvaluator']
    if len(network) != len(evaluations) - 1:
        raise ValueError('unexpected extra evaluator type')
    saved_mutation = kind == 'mutate' and status == 'SUCCESS'
    if saved_mutation and not network:
        raise ValueError('successful mutation lacks network assertion')
    return {'task_type': kind, 'expected_status': status,
            'successful_mutation_expected': saved_mutation,
            'network_assertions': len(network),
            'network_only_for_mutation': saved_mutation,
            'requires_saved_state_oracle': saved_mutation,
            'requires_no_state_change_oracle': kind == 'mutate' and status == 'ACTION_NOT_ALLOWED_ERROR',
            'requires_browser_trace_oracle': kind == 'retrieve' and not network}


def entity_hints(row: dict) -> list[str]:
    """Extract only obvious source-entity hints; absence means unaudited.

    These hints are not trusted disjointness keys because task instructions can
    refer to entities indirectly or share underlying database records.
    """
    params = row.get('instantiation_dict') or {}
    keys = ('order_id', 'order', 'id', 'product', 'product_id', 'config', 'brand', 'PhoneNum', 'page_id', 'cms_page_id')
    hints = []
    for key in keys:
        value = params.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            normalized = re.sub(r'\s+', ' ', str(value).strip().lower())
            hints.append(key.lower() + ':' + normalized)
    # CMS page IDs can appear only in the published network assertion's form
    # fields. Record the explicit entity ID without copying its desired title.
    for evaluation in row.get('eval', [])[1:]:
        expected = evaluation.get('expected', {})
        post_data = expected.get('post_data', {})
        if isinstance(post_data, dict):
            value = post_data.get('page_id')
            if isinstance(value, (str, int)) and re.fullmatch(r'\d+', str(value)):
                hints.append('page_id:' + str(value))
        urls = expected.get('url')
        for value in ([urls] if isinstance(urls, str) else urls if isinstance(urls, list) else []):
            if not isinstance(value, str):
                continue
            if '/cms/page/' in value:
                for page_id in re.findall(r'/(?:page_id|id)/(\d+)(?:/|$)', value):
                    hints.append('page_id:' + page_id)
            if '/catalog/product/' in value:
                for product_id in re.findall(r'/catalog/product/(?:save|edit)/id/(\d+)(?:/|$)', value):
                    hints.append('product_id:' + product_id)
    return sorted(set(hints))


def task_record(row: dict, hard: set[int]) -> dict:
    shape = evaluation_shape(row)
    return {
        'task_id': row['task_id'],
        'task_record_sha256': digest(canonical_bytes(row)),
        'template_group': 'shopping_admin:' + str(row['intent_template_id']),
        'official_hard_subset': row['task_id'] in hard,
        'source_entity_hints': entity_hints(row),
        **shape,
    }


def choice_hash(value: str) -> str:
    return digest((SEED + ':' + value).encode('utf-8'))


def choose(rows: list[dict], hard: set[int], *, selection_count: int = 20,
           final_count: int = 100) -> dict:
    if len(rows) != 182:
        raise ValueError('expected 182 Magento source tasks')
    exposed_rows = [row for row in rows if row['task_id'] in EXPOSED_SOURCE_TASK_IDS]
    if len(exposed_rows) != len(EXPOSED_SOURCE_TASK_IDS):
        raise ValueError('development-exposed task identity missing from pinned source')
    exposed_entity_hints = {hint for row in exposed_rows for hint in entity_hints(row)}
    exposed_template_ids = {row['intent_template_id'] for row in exposed_rows}
    if not exposed_template_ids.issubset(QUARANTINED_TEMPLATES):
        raise ValueError('development-exposed template family is not quarantined')
    if not TRAIN_RESERVED_TASK_IDS.issubset(EXPOSED_SOURCE_TASK_IDS):
        raise ValueError('train reservation must also be marked as source exposure')
    allowed = [row for row in rows if row['intent_template_id'] not in QUARANTINED_TEMPLATES
               and row['task_id'] not in QUARANTINED_TASKS
               and evaluation_shape(row)['expected_status'] == 'SUCCESS'
               and not exposed_entity_hints.intersection(entity_hints(row))]
    groups: dict[int, list[dict]] = defaultdict(list)
    for row in allowed:
        groups[row['intent_template_id']].append(task_record(row, hard))
    for group in groups.values():
        group.sort(key=lambda item: choice_hash('task:' + str(item['task_id'])))

    # Guarantee one selection family per task type, then fill with hashed
    # whole families. All tasks in a selected family are held from final.
    selected_templates: list[int] = []
    for kind in ('mutate', 'retrieve', 'navigate'):
        candidates = [template for template, tasks in groups.items()
                      if template not in selected_templates and tasks[0]['task_type'] == kind]
        chosen = min(candidates, key=lambda template: choice_hash(f'{kind}:{template}'))
        selected_templates.append(chosen)
    remaining = sorted((template for template in groups if template not in selected_templates),
                       key=lambda template: choice_hash('selection-template:' + str(template)))
    while sum(len(groups[t]) for t in selected_templates) < selection_count:
        if not remaining:
            raise ValueError('insufficient selection templates')
        selected_templates.append(remaining.pop(0))
    selected_pool = [item for template in selected_templates for item in groups[template]]
    selection = sorted(selected_pool, key=lambda item: choice_hash('selection-task:' + str(item['task_id'])))[:selection_count]

    selection_hints = {hint for item in selected_pool
                       for hint in item['source_entity_hints']}
    nonselection_pool = [item for template, tasks in groups.items()
                         if template not in selected_templates for item in tasks]
    # Even the obvious cross-template entity overlap must be excluded. This
    # does not prove that subtler shared database records have been found.
    overlapping_hint_tasks = [item for item in nonselection_pool
                              if selection_hints.intersection(item['source_entity_hints'])]
    final_pool = [item for item in nonselection_pool
                  if not selection_hints.intersection(item['source_entity_hints'])]
    # Official hard IDs and persistent mutations are qualification priorities,
    # not proof of task difficulty, real saved state, or hidden evaluation.
    final_pool.sort(key=lambda item: (
        not item['official_hard_subset'],
        TASK_TYPE_ORDER[item['task_type']],
        -item['network_assertions'],
        choice_hash('final-task:' + str(item['task_id']))))
    if len(final_pool) < final_count:
        raise ValueError('fewer than 100 final candidates after template quarantine and selection isolation')
    final = final_pool[:final_count]
    if set(item['template_group'] for item in selection) & set(item['template_group'] for item in final):
        raise AssertionError('selection/final template leakage')
    if len({item['task_id'] for item in selection + final}) != selection_count + final_count:
        raise AssertionError('selection/final task ID reuse')
    return {'selection': selection, 'provisional_final': final,
            'selection_template_ids': sorted(selected_templates),
            'exposed_entity_overlap_excluded_tasks': sum(
                row['intent_template_id'] not in QUARANTINED_TEMPLATES
                and row['task_id'] not in QUARANTINED_TASKS
                and bool(exposed_entity_hints.intersection(entity_hints(row))) for row in rows),
            'reserved_selection_family_tasks': len(selected_pool) - len(selection),
            'obvious_source_entity_overlap_excluded_tasks': len(overlapping_hint_tasks),
            'unused_nonquarantined_tasks': len(final_pool) - len(final)}


def manifest(rows: list[dict], hard: set[int]) -> dict:
    sets = choose(rows, hard)
    categories = lambda task_rows: dict(sorted(Counter(row['task_type'] for row in task_rows).items()))
    hard_counts = lambda task_rows: sum(row['official_hard_subset'] for row in task_rows)
    quarantined = [row['task_id'] for row in rows if row['intent_template_id'] in QUARANTINED_TEMPLATES
                   or row['task_id'] in QUARANTINED_TASKS]
    return {
        'schema': 'cua-magento-admission-backlog-v0.6',
        'status': 'offline_provisional_final_candidates_not_officially_admitted',
        'source': {'commit': SOURCE_COMMIT, 'dataset_sha256': SOURCE_SHA256,
                   'hard_subset_sha256': HARD_SHA256,
                   'url': 'https://github.com/ServiceNow/webarena-verified'},
        'quarantine': {'template_ids': sorted(QUARANTINED_TEMPLATES),
                       'task_ids': sorted(quarantined),
                       'development_exposed_task_ids': sorted(EXPOSED_SOURCE_TASK_IDS),
                       'train_reserved_task_ids': sorted(TRAIN_RESERVED_TASK_IDS),
                       'template_reasons': {str(key): value for key, value in QUARANTINED_TEMPLATES.items()},
                       'task_reasons': {str(key): value for key, value in QUARANTINED_TASKS.items()},
                       'scope': 'provisional qualification quarantine; not a global invalidity claim'},
        'counts': {
            'published_admin_task_ids': 182,
            'published_intent_templates': 41,
            'published_hard_subset_admin_ids': sum(row['task_id'] in hard for row in rows),
            'source_non_success_outcomes_excluded': dict(sorted(Counter(
                evaluation_shape(row)['expected_status'] for row in rows
                if evaluation_shape(row)['expected_status'] != 'SUCCESS').items())),
            'quarantined_task_ids': len(quarantined),
            'exposed_entity_overlap_excluded_tasks': sets['exposed_entity_overlap_excluded_tasks'],
            'selection_instances': len(sets['selection']),
            'selection_template_families': len({row['template_group'] for row in sets['selection']}),
            'selection_reserved_same_family_tasks': sets['reserved_selection_family_tasks'],
            'obvious_source_entity_overlap_excluded_tasks': sets['obvious_source_entity_overlap_excluded_tasks'],
            'provisional_final_instances': len(sets['provisional_final']),
            'provisional_final_template_families': len({row['template_group'] for row in sets['provisional_final']}),
            'provisional_final_hard_subset_ids': hard_counts(sets['provisional_final']),
            'provisional_final_task_types': categories(sets['provisional_final']),
            'provisional_final_expected_statuses': dict(sorted(Counter(row['expected_status'] for row in sets['provisional_final']).items())),
            'provisional_final_successful_mutations': sum(row['successful_mutation_expected'] for row in sets['provisional_final']),
            'provisional_final_officially_admitted': 0,
            'unused_nonquarantined_task_ids': sets['unused_nonquarantined_tasks'],
        },
        'split_rule': 'Whole template families are reserved for selection, with one family per task type first; final candidates are template-disjoint, hard-subset and mutation prioritized, then hash-ordered.',
        'split_limitations': [
            'Public task IDs, instructions, and evaluators are not a sealed official final set.',
            'Obvious extracted source-entity hints are disjoint, but full database-record overlap across templates is not proven absent.',
            'Hard-subset membership and evaluator count are selection priorities, not validated difficulty or saved-state proof.',
            'Three individual source tasks are excluded pending policy-denial cohort design or evaluator repair; template 742 is held as accepted train-only technical data, while templates 240 and 275 are held as failed-contract development exposure.',
            'All 100 candidates still need GUI positive/negative, independent DB readback or answer provenance, full reset, and model observation/action gates.',
        ],
        'task_sets': {'selection': sets['selection'],
                      'provisional_final': sets['provisional_final']},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--hard-ids', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    rows, hard = source_rows(args.source, args.hard_ids)
    result = manifest(rows, hard)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result['counts'], sort_keys=True))


if __name__ == '__main__':
    main()
