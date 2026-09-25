"""Plan source-disjoint multi-variant pricing tasks on a pinned Magento catalog.

This is an offline *candidate* factory. It does not seed CMS quote pages, run a
browser, qualify per-ID GUI controls, train a model, or create a final score.
Private instructions, cost quotes, products and gold stay under ignored work/.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
from html import escape
import json
import os
from pathlib import Path
import random

from cursibench import scale_final_v06 as cell_final


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'envloop-magento-catalog-candidates-v1'
INVENTORY_SCHEMA = 'envloop-magento-catalog-private-inventory-v1'
INVENTORY_SHA256 = '742f505a16bdc9e478c2af2414455e50530ad824878c20254204314ccc5056cf'
MODELLED_SOURCE = 'Magento Open Source sample catalog plus synthetic supplier quotes'
SPLITS = {'train': 20, 'selection': 20, 'official_candidate': 100}
FINAL_TEMPLATES = (
    'multi-variant-margin-floor',
    'multi-variant-parity-ladder',
    'multi-variant-stock-promotion',
    'multi-variant-freight-surcharge',
)
NICKEL = Decimal('0.05')


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                      separators=(',', ':'),
                                      ensure_ascii=False,
                                      allow_nan=False).encode()).hexdigest()


def dollars(value: object) -> Decimal:
    result = Decimal(str(value))
    require(result.is_finite() and Decimal('1') <= result <= Decimal('10000'),
            'catalog price outside supported bound')
    return result


def nickel_up(value: Decimal) -> Decimal:
    return (value / NICKEL).to_integral_value(rounding=ROUND_CEILING) * NICKEL


def _rng(seed: str, label: str) -> random.Random:
    return random.Random(int.from_bytes(hashlib.sha256(
        f'{seed}:{label}'.encode()).digest(), 'big'))


def _case(seed: str, parent: dict, split: str, ordinal: int) -> dict:
    children = sorted(parent['children'], key=lambda row: row['entity_id'])
    rng = _rng(seed, f"{split}:{parent['parent_id']}")
    chosen = rng.sample(children, 1 if split == 'train' else
                        2 if split == 'selection' else 5)
    comparators = [row for row in children if row not in chosen][:2]
    template = ('single-visible-direct-reprice' if split == 'train' else
                'two-variant-quoted-reprice' if split == 'selection' else
                FINAL_TEMPLATES[ordinal % len(FINAL_TEMPLATES)])
    context_rows = []
    for index, child in enumerate(chosen):
        old = dollars(child['price'])
        if split == 'train':
            target = nickel_up(old * Decimal('0.88'))
            if target == old:
                target = nickel_up(old * Decimal('0.75'))
            source = {'direct_target_price': str(target)}
        elif split == 'selection':
            target = nickel_up(old * Decimal('0.91') + Decimal(index + 1))
            if target == old:
                target += NICKEL
            source = {'quoted_target_price': str(target)}
        elif template == 'multi-variant-margin-floor':
            cost = (old * Decimal('0.57') + Decimal(index + 1)).quantize(Decimal('0.01'))
            margin = Decimal('0.34') if index % 2 == 0 else Decimal('0.31')
            target = nickel_up(cost / (Decimal(1) - margin))
            while target == old:
                cost += Decimal('0.50')
                target = nickel_up(cost / (Decimal(1) - margin))
            source = {'supplier_cost': str(cost), 'gross_margin_floor': str(margin)}
        elif template == 'multi-variant-parity-ladder':
            anchor = nickel_up(old * Decimal('0.82'))
            increment = Decimal('1.75') + Decimal(index) * Decimal('0.50')
            target = nickel_up(anchor + increment)
            while target == old:
                increment += Decimal('0.25')
                target = nickel_up(anchor + increment)
            source = {'anchor_price': str(anchor), 'tier_increment': str(increment)}
        elif template == 'multi-variant-stock-promotion':
            stock = 8 + (index * 7) + rng.randrange(0, 4)
            threshold = 20
            discount = Decimal('0.17') if stock >= threshold else Decimal('0.07')
            target = nickel_up(old * (Decimal(1) - discount))
            source = {'quoted_stock_units': stock, 'threshold_units': threshold,
                      'discount_if_at_least_threshold': '0.17',
                      'discount_otherwise': '0.07'}
        else:
            freight_class = index + 1
            cost = (old * Decimal('0.54') + Decimal(index + 2)).quantize(Decimal('0.01'))
            rate = Decimal('1.25')
            target = nickel_up(cost / Decimal('0.68') + Decimal(freight_class) * rate)
            while target == old:
                rate += Decimal('0.25')
                target = nickel_up(cost / Decimal('0.68') +
                                   Decimal(freight_class) * rate)
            source = {'supplier_cost': str(cost),
                      'gross_margin_floor': '0.32',
                      'freight_class': freight_class,
                      'freight_usd_per_class': str(rate)}
        require(target > 0 and target != old,
                'policy failed to create a meaningful price target')
        context_rows.append({'entity_id': child['entity_id'], 'sku': child['sku'],
                             'initial_price': str(old), 'target_price': str(target),
                             'source_facts': source})
    opaque = digest({'seed': seed, 'split': split,
                     'parent_id': parent['parent_id']})[:16]
    task_id = f'magento-catalog-{opaque}'
    quote_name = f'Supplier cost review {opaque}'
    policy = {
        'single-visible-direct-reprice': 'Use the approved list price shown for the one named SKU.',
        'two-variant-quoted-reprice': 'Use the two approved list prices shown for the named SKUs.',
        'multi-variant-margin-floor': 'For each SKU, divide supplier cost by (1 - gross margin floor), then round UP to the next $0.05.',
        'multi-variant-parity-ladder': 'For each SKU, add its tier increment to its anchor price, then round UP to the next $0.05.',
        'multi-variant-stock-promotion': 'For each SKU, discount its current list price by 17% when quoted stock is at least 20 units, otherwise by 7%; round UP to the next $0.05.',
        'multi-variant-freight-surcharge': 'For each SKU, divide supplier cost by (1 - gross margin floor), add freight class times freight USD per class, then round UP to the next $0.05.',
    }[template]
    columns = sorted({key for row in context_rows for key in row['source_facts']})
    cells = []
    for row in context_rows:
        source = row['source_facts']
        values = [row['sku'], row['initial_price']] + [str(source.get(key, '')) for key in columns]
        cells.append('<tr>' + ''.join(f'<td>{escape(value)}</td>' for value in values) + '</tr>')
    header = ['SKU', 'Current list price'] + [key.replace('_', ' ').title() for key in columns]
    quote_body = ('<h1>' + escape(quote_name) + '</h1><p>' + escape(policy) +
                  '</p><table><thead><tr>' +
                  ''.join(f'<th>{escape(value)}</th>' for value in header) +
                  '</tr></thead><tbody>' + ''.join(cells) +
                  '</tbody></table><p>Only the named SKUs are in scope. Preserve all other catalog and business records.</p>')
    instruction = (f'In Content > Pages, open "{quote_name}" for configurable '
                   f'product {parent["parent_sku"]}. Apply its {template.replace("-", " ")} '
                   'policy to the named child SKUs in Catalog and save them. '
                   'Preserve every other variant and business record.')
    case = {'task_id': task_id, 'split': split,
            'parent_id': parent['parent_id'], 'parent_sku': parent['parent_sku'],
            'source_family': f"magento-parent:{parent['parent_id']}",
            'instance_group': f"magento-parent-world:{parent['parent_id']}",
            'template_group': template, 'quote_page_title': quote_name,
            'quote_page_body': quote_body,
            'quote_page_body_sha256': hashlib.sha256(quote_body.encode()).hexdigest(),
            'instruction': instruction,
            'policy_kind': template, 'target_variants': context_rows,
            'untouched_comparators': [{key: row[key] for key in ('entity_id', 'sku', 'price')}
                                      for row in comparators],
            'source_type': MODELLED_SOURCE,
            'gui_positive_passed': False,
            'gui_negative_passed': False,
            'fresh_reset_passed': False,
            'official_final_admitted': False}
    case['package_sha256'] = digest(case)
    return case


def identity(case: dict) -> dict:
    return {'task_id': case['task_id'],
            'package_sha256': case['package_sha256'],
            'source_groups': [case['source_family']],
            'template_group': case['template_group'],
            'instance_group': case['instance_group']}


def build(inventory: dict, inventory_sha256: str, seed: str) -> dict:
    require(inventory_sha256 == INVENTORY_SHA256 and
            inventory.get('schema') == INVENTORY_SCHEMA and
            len(seed) >= 32 and
            inventory.get('docker_image_sha256', '').startswith('sha256:'),
            'pinned inventory or private seed mismatch')
    quarantine = set(inventory['quarantined_parent_ids'])
    parents = [row for row in inventory['parents']
               if len(row['children']) >= 5 and row['parent_id'] not in quarantine]
    require(len({row['parent_id'] for row in parents}) == len(parents) and
            len(parents) >= 140, 'insufficient disjoint configurable parents')
    finals = sorted((row for row in parents if len(row['children']) >= 10),
                    key=lambda row: digest({'seed': seed, 'cohort': 'final',
                                            'parent': row['parent_sku']}))[:100]
    require(len(finals) == 100, 'fewer than 100 ten-variant final parents')
    final_ids = {row['parent_id'] for row in finals}
    remaining = sorted((row for row in parents if row['parent_id'] not in final_ids),
                       key=lambda row: digest({'seed': seed, 'cohort': 'dev',
                                               'parent': row['parent_sku']}))
    require(len(remaining) >= 40, 'no disjoint training and selection reserve')
    selected = {'train': remaining[:20], 'selection': remaining[20:40],
                'official_candidate': finals}
    cases = {split: [_case(seed, parent, split, ordinal)
                     for ordinal, parent in enumerate(rows)]
             for split, rows in selected.items()}
    task_sets = {'train': [identity(case) for case in cases['train']],
                 'selection': [identity(case) for case in cases['selection']],
                 'official': [identity(case) for case in cases['official_candidate']]}
    cell_final.validate_splits(task_sets)
    require(len({case['task_id'] for rows in cases.values() for case in rows}) == 140,
            'task identity collision')
    output = {
        'schema': SCHEMA, 'status': 'offline_candidates_not_gui_admitted',
        'inventory_sha256': inventory_sha256,
        'private_seed_sha256': hashlib.sha256(seed.encode()).hexdigest(),
        'application': 'Magento Open Source 2.4.6 admin',
        'source_type': MODELLED_SOURCE,
        'split_counts': {key: len(value) for key, value in cases.items()},
        'final_source_family_count': 100,
        'final_template_counts': {name: sum(case['template_group'] == name
                                            for case in cases['official_candidate'])
                                  for name in FINAL_TEMPLATES},
        'train_template_groups': sorted({case['template_group'] for case in cases['train']}),
        'selection_template_groups': sorted({case['template_group'] for case in cases['selection']}),
        'final_template_groups': sorted({case['template_group'] for case in cases['official_candidate']}),
        'task_sets': task_sets,
        'cases': cases,
        'official_final_admitted_count': 0,
        'model_scores_present': False,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, required=True)
    parser.add_argument('--seed-file', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    require(out.is_relative_to((ROOT / 'work').resolve()) and not out.exists(),
            'new private work/ output required')
    raw_inventory = args.inventory.read_bytes()
    seed = args.seed_file.read_text().strip()
    plan = build(json.loads(raw_inventory), hashlib.sha256(raw_inventory).hexdigest(), seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(plan, indent=2, sort_keys=True) + '\n').encode()
    descriptor = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'status': plan['status'], 'split_counts': plan['split_counts'],
                      'final_source_family_count': plan['final_source_family_count'],
                      'final_template_counts': plan['final_template_counts'],
                      'private_plan_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_final_admitted_count': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
