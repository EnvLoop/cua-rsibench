"""Publish an aggregate receipt for one train-only Magento sidecar GUI trio.

Task text, SKU, quote, prices, screenshots, login and raw snapshots stay in
ignored evaluator storage. This tool cannot admit a final task or model score.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import IMAGE, load_case
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_HOST, NATIVE_SEARCH_IMAGE, NATIVE_SEARCH_NETWORK,
    score_saved_state,
)


PRIVATE = ROOT / 'work/magento-original'
PUBLIC = ROOT / 'docs/evidence/magento-original-native-search-train-control-2026-09-25.json'
PLAN_SHA = '1df41f027b5f284c7ff7ed162f42f075259960242a295e0a430bff1c8b479ae1'
INPUTS = {
    'neutral_first': 'train-neutral-sidecar-1/result.json',
    'positive': 'train-control-positive-sidecar-1/result.json',
    'neutral_second': 'train-neutral-sidecar-2/result.json',
    'wrong_variant': 'train-control-wrong-variant-sidecar-1/result.json',
    'finalization_first': 'clone4-sidecar-finalization.private.json',
    'finalization_second': 'clone5-sidecar-finalization.private.json',
    'runtime_first': 'clone4-sidecar-runtime.private.json',
    'runtime_second': 'clone5-sidecar-runtime.private.json',
    'fresh_reset': 'train-sidecar-fresh-reset.private.json',
    'strict_before': 'train-control-positive-7/private-before.json',
    'strict_after': 'train-control-positive-7/private-after.json',
}


def load(name: str) -> tuple[dict, str]:
    path = PRIVATE / INPUTS[name]
    require(path.resolve().is_relative_to(PRIVATE.resolve()) and path.is_file()
            and (path.stat().st_mode & 0o077) == 0,
            'private receipt missing or broadly readable')
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build() -> dict:
    plan = json.loads((PRIVATE / 'candidate-plan-v2.private.json').read_bytes())
    case = plan['cases']['train'][0]
    case = load_case(PRIVATE / 'candidate-plan-v2.private.json',
                     PLAN_SHA, case['task_id'])
    loaded = {key: load(key) for key in INPUTS}
    values = {key: pair[0] for key, pair in loaded.items()}
    hashes = {key: pair[1] for key, pair in loaded.items()}
    require(all(values[key]['task_id'] == case['task_id'] for key in
                ('neutral_first', 'positive', 'neutral_second',
                 'wrong_variant', 'fresh_reset')),
            'train-only task identity changed')
    for name in ('neutral_first', 'neutral_second'):
        record = values[name]
        require(record['mode'] == 'neutral' and
                record['status'] == 'neutral_fixture_normalization_development_only' and
                record['neutral_preserved_other_business_state'] is True and
                record['search_backend'] == NATIVE_SEARCH_HOST and
                record['model_calls'] == 0,
                'neutral native-control receipt changed')
    positive, negative = values['positive'], values['wrong_variant']
    require(positive['mode'] == 'positive' and
            positive['score']['score'] == 1.0 and
            negative['mode'] == 'wrong-variant' and
            negative['score']['score'] == 0.0 and
            'untouched_variant_changed' in negative['score']['failure_codes'] and
            positive['quote']['quote_visible_in_native_cms'] and
            negative['quote']['quote_visible_in_native_cms'] and
            positive['search_backend'] == negative['search_backend'] ==
            NATIVE_SEARCH_HOST and
            positive['model_calls'] == negative['model_calls'] == 0,
            'native positive/negative GUI controls changed')
    first, second = (values['finalization_first'],
                     values['finalization_second'])
    require(first['normalized_baseline_sha256'] ==
            second['normalized_baseline_sha256'] ==
            positive['before_sha256'] == negative['before_sha256'] and
            first['search_backend'] == second['search_backend'] ==
            NATIVE_SEARCH_HOST and
            values['fresh_reset']['fresh_clone_reset_passed'] is True and
            values['fresh_reset']['different_container_ids'] is True and
            values['fresh_reset']['different_search_container_ids'] is True,
            'same-topology frozen baseline/reset did not match')
    app_ids = {values[name]['app']['container_id_sha256']
               for name in ('runtime_first', 'runtime_second')}
    search_ids = {values[name]['sidecar_id_sha256']
                  for name in ('runtime_first', 'runtime_second')}
    require(len(app_ids) == len(search_ids) == 2 and
            all(values[name]['app']['image_sha256'] == IMAGE and
                values[name]['sidecar_image_sha256'] == NATIVE_SEARCH_IMAGE and
                values[name]['network'] == NATIVE_SEARCH_NETWORK
                for name in ('runtime_first', 'runtime_second')),
            'fresh pinned runtime identity changed')
    strict = score_saved_state(case, values['strict_before'],
                               values['strict_after'])
    require(strict['score'] == 0.0 and
            strict['failure_codes'] == ['target_nonprice_changed'],
            'pre-normalization strict rejection disappeared')
    before = values['strict_before']
    return {
        'schema': 'envloop-magento-original-native-search-train-control-public-v1',
        'status': 'train_only_development_trio_not_final_admission',
        'checked_date': '2026-09-25',
        'application': 'Magento Open Source 2.4.6 admin',
        'app_image_sha256': IMAGE,
        'native_search_image_sha256': NATIVE_SEARCH_IMAGE,
        'native_search_architecture': 'arm64',
        'native_search_version': '7.10.2 OSS',
        'app_architecture': 'amd64',
        'same_topology_distinct_app_containers': 2,
        'same_topology_distinct_search_containers': 2,
        'search_document_count': before['search']['document_count'],
        'search_document_baseline_sha256': before['search']['full_sha256'],
        'monitored_catalog_table_count': len(before['database']['hashes']['other_catalog']),
        'monitored_other_business_table_count': len(before['database']['hashes']['business']),
        'pre_normalization_strict_positive_score': 0.0,
        'pre_normalization_failure_codes': strict['failure_codes'],
        'neutral_saves_preserved_non_target_business_state': 2,
        'normalized_gui_positive_score': 1.0,
        'wrong_variant_gui_negative_score': 0.0,
        'wrong_variant_failure_codes': negative['score']['failure_codes'],
        'fresh_same_topology_exact_reset_passed': True,
        'frozen_normalized_baseline_sha256': first['normalized_baseline_sha256'],
        'private_receipt_sha256': hashes,
        'model_calls': 0,
        'official_final_tasks_admitted': 0,
        'researcher_campaigns': 0,
        'known_limit': ('One evaluator-scripted train-only parent. Final 100 identities, '
                        'per-ID GUI controls, researcher action contract, and model '
                        'difficulty remain unqualified.'),
    }


def main() -> None:
    require(not PUBLIC.exists(), 'new public receipt path required')
    value = build()
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(PUBLIC, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
    print(json.dumps({'status': value['status'],
                      'receipt_sha256': hashlib.sha256(raw).hexdigest(),
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
