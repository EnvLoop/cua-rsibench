"""Reduce one private Tinker hourly billing export to field-limited GUI SFT evidence.

The input must already be filtered to the task-777 smoke session. This tool
never calls a provider or prints session, account, project, or user identities.
Hourly usage is provider-reported; published-rate dollars are not an invoice.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path


MODEL = 'Qwen/Qwen3.8-27B'
PURPOSE = 'magento-price777-gui-sft-checkpoint-smoke-v1'
KINDS = {'training': 'train', 'sampling_prefill': 'prefill',
         'sampling_sample': 'sample'}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rate(text: object, label: str) -> Decimal:
    require(isinstance(text, str) and text.startswith('$'), f'{label}: price required')
    try:
        value = Decimal(text[1:])
    except InvalidOperation:
        raise ValueError(f'{label}: invalid price') from None
    require(value.is_finite() and value >= 0, f'{label}: nonnegative price required')
    return value


def utc(value: object) -> datetime:
    require(isinstance(value, str), 'UTC timestamp required')
    try:
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('invalid UTC timestamp') from None
    require(timestamp.tzinfo is not None and timestamp.utcoffset().total_seconds() == 0,
            'UTC timestamp required')
    return timestamp.astimezone(timezone.utc)


def reconcile(usage: object, pricing: object, *, usage_sha256: str,
              pricing_sha256: str) -> dict:
    require(isinstance(usage, dict) and
            usage.get('schema') == 'envloop-price777-private-billing-filter-v1' and
            isinstance(usage.get('events'), list) and
            isinstance(usage.get('sessions'), dict),
            'filtered billing export required')
    start, end = utc(usage.get('window_start')), utc(usage.get('window_end'))
    require(start < end and end - start <= timedelta(days=14), 'billing window invalid')
    sessions = usage['sessions']
    require(len(sessions) == 1, 'exactly one benchmark smoke session required')
    for session in sessions.values():
        metadata = session.get('user_metadata') if isinstance(session, dict) else None
        require(isinstance(metadata, dict) and
                metadata.get('purpose') == PURPOSE and
                metadata.get('split') == 'train' and
                metadata.get('source_task_id') == '777',
                'session metadata does not identify train-only smoke')
    require(isinstance(pricing, list), 'official model pricing array required')
    models = [row for row in pricing if isinstance(row, dict) and
              row.get('tinker_id') == MODEL]
    require(len(models) == 1 and 'Vision' in str(models[0].get('type', '')),
            'exact vision model pricing row required')
    prices = {key: rate(models[0].get(key), key)
              for key in ('prefill', 'cached_prefill', 'sample', 'train')}
    tokens = {'training': 0, 'sampling_prefill_uncached': 0,
              'sampling_prefill_cached': 0, 'sampling_sample': 0}
    counts = {key: 0 for key in tokens}
    nominal = Decimal(0)
    unpriced = 0
    for event in usage['events']:
        require(isinstance(event, dict) and
                event.get('session_id') in sessions and
                event.get('base_model') == MODEL and
                start <= utc(event.get('bucket_start')) < end and
                isinstance(event.get('event_info'), dict),
                'billing event identity or window changed')
        info = event['event_info']
        kind = info.get('type')
        if kind not in KINDS:
            unpriced += 1
            continue
        quantity = info.get('token_count')
        require(type(quantity) is int and quantity >= 0,
                'nonnegative billed token count required')
        if kind == 'sampling_prefill':
            require(type(info.get('cached')) is bool, 'prefill cache flag required')
            cached = info['cached']
            category = 'sampling_prefill_cached' if cached else 'sampling_prefill_uncached'
            unit = prices['cached_prefill' if cached else 'prefill']
        else:
            category = kind
            unit = prices[KINDS[kind]]
        tokens[category] += quantity
        counts[category] += 1
        nominal += Decimal(quantity) * unit / Decimal(1_000_000)
    require(counts['training'] == 1 and
            counts['sampling_prefill_uncached'] + counts['sampling_prefill_cached'] == 1 and
            counts['sampling_sample'] == 1,
            'one-step training and one checkpoint sample usage not reconciled')
    return {
        'schema': 'envloop-price777-tinker-billing-reconciliation-v1',
        'source_task_id': 777, 'model': MODEL,
        'train_only_development': True,
        'window_start': usage['window_start'],
        'window_end': usage['window_end'],
        'private_filtered_usage_sha256': usage_sha256,
        'official_models_json_sha256': pricing_sha256,
        'matched_session_count': 1,
        'matched_hourly_event_count': len(usage['events']),
        'event_count_by_type': counts,
        'provider_reported_billed_tokens_by_type': tokens,
        'unpriced_event_count': unpriced,
        'published_rate_usd_per_million': {key: str(value)
                                           for key, value in prices.items()},
        'published_rate_nominal_token_subtotal_usd': str(nominal),
        'provider_invoice_usd': None,
        'checkpoint_storage_and_credit_adjustments_known': False,
        'hourly_billing_lag_possible': True,
        'official_final_results_added': 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filtered-usage', type=Path, required=True)
    parser.add_argument('--pricing', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw_usage = args.filtered_usage.read_bytes()
    raw_pricing = args.pricing.read_bytes()
    result = reconcile(json.loads(raw_usage), json.loads(raw_pricing),
                       usage_sha256=sha(raw_usage), pricing_sha256=sha(raw_pricing))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps({'status': 'reconciled',
                      'provider_reported_training_tokens':
                          result['provider_reported_billed_tokens_by_type']['training'],
                      'published_rate_nominal_token_subtotal_usd':
                          result['published_rate_nominal_token_subtotal_usd'],
                      'provider_invoice_usd': None}, sort_keys=True))


if __name__ == '__main__':
    main()
