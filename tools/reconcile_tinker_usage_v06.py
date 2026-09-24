"""Reconcile one v0.6 campaign's Tinker hourly events with published rates.

Input is a private dump of RestClient.get_billing_usage(). This is a nominal
token-rate estimate, not an invoice or an all-in benchmark cost. Storage,
checkpoint, provider credits and unpublished discounts remain unknown.
No API keys or network calls are used by this offline reducer.
"""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


MODEL = 'Qwen/Qwen3.8-27B'
PURPOSES = frozenset({'scale-vision-proxy-v1', 'cua-v06-training'})
CAMPAIGN_ID = re.compile(r'[a-z][a-z0-9-]{0,63}\Z')
TOKEN_KINDS = {'training': 'train', 'sampling_prefill': 'prefill',
               'sampling_sample': 'sample'}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def utc_hour(value):
    require(isinstance(value, str), 'UTC hour required')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('invalid UTC hour') from None
    require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)
            and parsed.minute == parsed.second == parsed.microsecond == 0,
            'UTC hour boundary required')
    return parsed.astimezone(timezone.utc)


def price(value):
    require(isinstance(value, str) and value.startswith('$'), 'published price missing')
    try:
        number = Decimal(value[1:])
    except InvalidOperation:
        raise ValueError('invalid published price') from None
    require(number.is_finite() and number >= 0, 'invalid published price')
    return number


def rates(pricing):
    require(isinstance(pricing, list), 'pricing must be the official models.json array')
    rows = [row for row in pricing if isinstance(row, dict) and row.get('tinker_id') == MODEL]
    require(len(rows) == 1, 'exact Qwen3.8-27B pricing row required')
    row = rows[0]
    require('Vision' in str(row.get('type', '')), 'pricing model must support vision')
    return {key: price(row[key]) for key in ('prefill', 'cached_prefill', 'sample', 'train')}


def reconcile(usage, pricing, *, campaign_id, window_start, window_end,
              usage_sha256=None, pricing_sha256=None):
    require(isinstance(campaign_id, str) and CAMPAIGN_ID.fullmatch(campaign_id),
            'invalid campaign ID')
    start, end = utc_hour(window_start), utc_hour(window_end)
    require(start < end and end - start <= timedelta(days=14), 'usage window out of bounds')
    require(isinstance(usage, dict) and isinstance(usage.get('data'), list)
            and isinstance(usage.get('sessions'), dict), 'billing usage response incomplete')
    rate = rates(pricing)
    tokens = {'training': 0, 'sampling_prefill_uncached': 0,
              'sampling_prefill_cached': 0, 'sampling_sample': 0}
    dollar = {key: Decimal(0) for key in tokens}
    matched, unattributed, unpriced = 0, 0, 0
    for event in usage['data']:
        require(isinstance(event, dict) and isinstance(event.get('event_info'), dict),
                'invalid billing event')
        bucket = utc_hour(event.get('bucket_start'))
        require(start <= bucket < end, 'billing event outside requested window')
        session_id = event.get('session_id')
        if not isinstance(session_id, str) or session_id not in usage['sessions']:
            unattributed += 1
            continue
        session = usage['sessions'][session_id]
        require(isinstance(session, dict), 'invalid session metadata')
        metadata = session.get('user_metadata')
        if not isinstance(metadata, dict):
            unattributed += 1
            continue
        if metadata.get('campaign_id') != campaign_id or metadata.get('purpose') not in PURPOSES:
            continue
        matched += 1
        info = event['event_info']
        kind = info.get('type')
        if event.get('base_model') != MODEL or kind not in TOKEN_KINDS:
            unpriced += 1
            continue
        count = info.get('token_count')
        require(type(count) is int and count >= 0, 'invalid billed token count')
        if kind == 'sampling_prefill':
            require(type(info.get('cached')) is bool, 'prefill cache flag required')
            category = 'sampling_prefill_cached' if info['cached'] else 'sampling_prefill_uncached'
            unit = rate['cached_prefill' if info['cached'] else 'prefill']
        else:
            category = kind
            unit = rate[TOKEN_KINDS[kind]]
        tokens[category] += count
        dollar[category] += Decimal(count) * unit / Decimal(1_000_000)
    subtotal = sum(dollar.values(), Decimal(0))
    return {
        'schema': 'v0.6-tinker-usage-reconciliation-v1',
        'campaign_id': campaign_id, 'model': MODEL, 'purposes': sorted(PURPOSES),
        'window_start': window_start, 'window_end': window_end,
        'usage_sha256': usage_sha256, 'pricing_sha256': pricing_sha256,
        'matched_event_count': matched, 'unattributed_org_event_count': unattributed,
        'unpriced_campaign_event_count': unpriced,
        'billed_tokens_by_type': tokens,
        'published_rate_usd_per_million': {key: str(value) for key, value in rate.items()},
        'nominal_token_rate_subtotal_usd': str(subtotal),
        'all_in_cost_usd': None, 'provider_invoice_or_credit_adjustment_included': False,
        'billing_freshness_complete': None,
        'interpretation': 'Hourly billing events may lag by hours; this is an attributed published-rate token subtotal, not an invoice or available-balance proof.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--usage', type=Path, required=True)
    parser.add_argument('--pricing', type=Path, required=True)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--window-start', required=True)
    parser.add_argument('--window-end', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw_usage, raw_pricing = args.usage.read_bytes(), args.pricing.read_bytes()
    result = reconcile(json.loads(raw_usage), json.loads(raw_pricing),
        campaign_id=args.campaign_id, window_start=args.window_start,
        window_end=args.window_end, usage_sha256=sha(raw_usage),
        pricing_sha256=sha(raw_pricing))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'status': 'reconciled', 'campaign_id': args.campaign_id,
                      'matched_events': result['matched_event_count'],
                      'nominal_token_rate_subtotal_usd': result['nominal_token_rate_subtotal_usd'],
                      'all_in_cost_usd': None}))


if __name__ == '__main__':
    main()
