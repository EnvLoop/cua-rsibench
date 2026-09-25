"""Durable dollar reservations for the frozen 24-campaign study.

Every external call reserves its worst-case nominal envelope before dispatch.
An uncertain response remains reserved until a trusted usage or no-charge
receipt resolves it. This is a local controller, not a provider invoice.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
import fcntl
import json
import os
from pathlib import Path
import re

from . import full_study_pre_campaign_v1 as pre_campaign
from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-dollar-ledger-v1'
ATTEMPT = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}\Z')
CAMPAIGN_CATEGORIES = {
    'tinker': 'tinker_usd_cap',
    'researcher_inference': 'researcher_inference_usd_cap',
    'teacher_rollout': 'teacher_rollout_usd_cap',
    'e2b': 'e2b_usd_cap',
    'storage_application': 'storage_application_usd_cap',
    'selected_final': 'selected_final_cost_upper_bound_usd',
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _dollar(value: object, label: str) -> Decimal:
    _require(isinstance(value, str), f'{label}: decimal string required')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise ValueError(f'{label}: invalid decimal') from None
    _require(amount.is_finite() and amount >= 0 and
             -amount.as_tuple().exponent <= 9,
             f'{label}: finite nonnegative amount with at most nine decimals required')
    return amount


def _hash(value: object, label: str) -> str:
    _require(cell_final.is_hash(value), f'{label}: SHA-256 required')
    return value


def _plan_limits(plan: object) -> tuple[str, Decimal, dict]:
    _require(isinstance(plan, dict) and plan.get('schema') == pre_campaign.PLAN_SCHEMA and
             plan.get('campaign_count') == 24 and
             plan.get('distinct_official_task_identities') == 600 and
             isinstance(plan.get('campaign_intents'), list) and
             len(plan['campaign_intents']) == 24 and
             isinstance(plan.get('cells'), list) and len(plan['cells']) == 6,
             'qualified pre-campaign plan required')
    limits = {}
    by_cell = {cell['cell_id']: cell for cell in plan['cells']}
    _require(len(by_cell) == 6, 'duplicate pre-campaign cell')
    for intent in plan['campaign_intents']:
        owner = f"{intent['cell_id']}:{intent['researcher_id']}"
        _require(owner not in limits and intent['cell_id'] in by_cell,
                 'duplicate or unknown campaign owner')
        category_caps = {name: _dollar(intent[field], field)
                         for name, field in CAMPAIGN_CATEGORIES.items()
                         if name != 'selected_final'}
        category_caps['selected_final'] = _dollar(
            by_cell[intent['cell_id']]['selected_final_cost_upper_bound_usd'],
            'selected_final_cost_upper_bound_usd')
        all_in = _dollar(intent['all_in_ceiling_usd'], 'all_in_ceiling_usd')
        _require(sum(category_caps.values(), Decimal(0)) <= all_in,
                 f'{owner}: category caps exceed campaign ceiling')
        limits[owner] = {'all_in': all_in, 'categories': category_caps}
    for cell_id, cell in by_cell.items():
        owner = f'{cell_id}:shared-base'
        amount = _dollar(cell['selected_final_cost_upper_bound_usd'],
                         'shared base final cost')
        limits[owner] = {'all_in': amount,
                         'categories': {'shared_base_final': amount}}
    global_cap = _dollar(plan['declared_all_in_cost_upper_bound_usd'],
                         'declared_all_in_cost_upper_bound_usd')
    _require(sum(row['all_in'] for row in limits.values()) == global_cap,
             'global ceiling differs from all campaign and base reserves')
    return cell_final.digest(cell_final.json_bytes(plan)), global_cap, limits


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


class StudyBudgetLedger:
    def __init__(self, path: str | Path, plan: dict):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.parent / ('.' + self.path.name + '.lock')
        self.plan_sha256, self.global_cap, self.limits = _plan_limits(plan)
        with self._lock():
            if not self.path.exists():
                header = {'schema': SCHEMA, 'kind': 'header',
                          'plan_sha256': self.plan_sha256,
                          'global_cap_usd': str(self.global_cap),
                          'limits_sha256': cell_final.digest(_canonical({
                              owner: {'all_in': str(row['all_in']),
                                      'categories': {name: str(cap) for name, cap in
                                                     row['categories'].items()}}
                              for owner, row in self.limits.items()})),
                          'previous': None}
                self._append(header)
            self._load()

    @contextmanager
    def _lock(self):
        with self.lock_path.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _append(self, record: dict) -> None:
        row = {**record, 'hash': cell_final.digest(_canonical(record))}
        with self.path.open('ab') as stream:
            stream.write(_canonical(row))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(self.path, 0o600)

    def _totals(self, state: dict) -> tuple[Decimal, dict]:
        by_owner = {owner: {'all_in': Decimal(0),
                            'categories': {name: Decimal(0) for name in row['categories']}}
                    for owner, row in self.limits.items()}
        for record in state.values():
            amount = (Decimal(0) if record['status'] == 'cancelled' else
                      _dollar(record['actual_usd'], 'actual_usd')
                      if record['status'] in ('settled', 'overrun') else
                      _dollar(record['reserved_usd'], 'reserved_usd'))
            owner = by_owner[record['owner']]
            owner['all_in'] += amount
            owner['categories'][record['category']] += amount
        global_used = sum((row['all_in'] for row in by_owner.values()), Decimal(0))
        return global_used, by_owner

    def _check_caps(self, state: dict) -> None:
        if any(record['status'] == 'overrun' for record in state.values()):
            # Preserve the provider's actual charge even when it violated the
            # reservation. The ledger is then terminal for new dispatch.
            return
        global_used, by_owner = self._totals(state)
        _require(global_used <= self.global_cap, 'global all-in reserve exhausted')
        for owner, row in by_owner.items():
            limits = self.limits[owner]
            _require(row['all_in'] <= limits['all_in'], f'{owner}: all-in cap exhausted')
            for category, amount in row['categories'].items():
                _require(amount <= limits['categories'][category],
                         f'{owner}/{category}: category cap exhausted')

    def _load(self) -> tuple[list[dict], dict]:
        rows = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        _require(rows, 'empty budget ledger')
        expected_limits = cell_final.digest(_canonical({
            owner: {'all_in': str(row['all_in']),
                    'categories': {name: str(cap) for name, cap in row['categories'].items()}}
            for owner, row in self.limits.items()}))
        previous = None
        state = {}
        for index, row in enumerate(rows):
            content = {key: value for key, value in row.items() if key != 'hash'}
            _require(row.get('previous') == previous and
                     row.get('hash') == cell_final.digest(_canonical(content)),
                     'budget ledger hash chain broken')
            previous = row['hash']
            if index == 0:
                _require(content == {'schema': SCHEMA, 'kind': 'header',
                                     'plan_sha256': self.plan_sha256,
                                     'global_cap_usd': str(self.global_cap),
                                     'limits_sha256': expected_limits,
                                     'previous': None},
                         'budget ledger frozen plan differs')
                continue
            kind = row.get('kind')
            attempt_id = row.get('attempt_id')
            _require(isinstance(attempt_id, str) and ATTEMPT.fullmatch(attempt_id),
                     'invalid budget attempt ID')
            if kind == 'reserve':
                _require(not any(old['status'] == 'overrun' for old in state.values()) and
                         attempt_id not in state and row.get('owner') in self.limits and
                         row.get('category') in self.limits[row['owner']]['categories'] and
                         _hash(row.get('work_sha256'), 'work') and
                         _dollar(row.get('reserved_usd'), 'reserved_usd') > 0,
                         'invalid dollar reservation')
                _require(not any(old['work_sha256'] == row['work_sha256'] and
                                 old['status'] != 'cancelled' for old in state.values()),
                         'same work already reserved or settled')
                state[attempt_id] = {'owner': row['owner'],
                                     'category': row['category'],
                                     'work_sha256': row['work_sha256'],
                                     'reserved_usd': row['reserved_usd'],
                                     'actual_usd': None,
                                     'status': 'pending', 'evidence_sha256': None}
            elif kind == 'dispatch_started':
                _require(attempt_id in state and
                         state[attempt_id]['status'] == 'pending' and
                         _hash(row.get('request_sha256'), 'exact request'),
                         'dispatch intent out of order')
                state[attempt_id]['status'] = 'dispatched'
                state[attempt_id]['request_sha256'] = row['request_sha256']
            elif kind == 'uncertain':
                _require(attempt_id in state and
                         state[attempt_id]['status'] == 'dispatched' and
                         row.get('failure_type') in
                         {'provider', 'transport', 'environment', 'verifier'},
                         'uncertain budget event out of order')
                state[attempt_id]['status'] = 'uncertain'
                state[attempt_id]['failure_type'] = row['failure_type']
            elif kind == 'settle':
                _require(attempt_id in state and
                         state[attempt_id]['status'] in ('dispatched', 'uncertain') and
                         _hash(row.get('evidence_sha256'), 'usage evidence') and
                         _dollar(row.get('actual_usd'), 'actual_usd') <=
                         _dollar(state[attempt_id]['reserved_usd'], 'reserved_usd'),
                         'settlement lacks trusted bounded usage')
                state[attempt_id].update(status='settled', actual_usd=row['actual_usd'],
                                         evidence_sha256=row['evidence_sha256'])
            elif kind == 'overrun':
                _require(attempt_id in state and
                         state[attempt_id]['status'] in ('dispatched', 'uncertain') and
                         _hash(row.get('evidence_sha256'), 'usage evidence') and
                         _dollar(row.get('actual_usd'), 'actual_usd') >
                         _dollar(state[attempt_id]['reserved_usd'], 'reserved_usd'),
                         'provider overrun evidence or amount invalid')
                state[attempt_id].update(status='overrun', actual_usd=row['actual_usd'],
                                         evidence_sha256=row['evidence_sha256'])
            elif kind == 'cancel':
                _require(attempt_id in state and
                         state[attempt_id]['status'] in ('pending', 'dispatched', 'uncertain') and
                         _hash(row.get('no_charge_sha256'), 'no-charge evidence'),
                         'cancellation lacks no-charge evidence')
                state[attempt_id].update(status='cancelled',
                                         evidence_sha256=row['no_charge_sha256'])
            else:
                raise ValueError('unknown budget event kind')
            self._check_caps(state)
        return rows, state

    def reserve(self, attempt_id: str, owner: str, category: str,
                amount_usd: str, work_sha256: str) -> dict:
        _require(isinstance(attempt_id, str) and ATTEMPT.fullmatch(attempt_id),
                 'invalid budget attempt ID')
        _hash(work_sha256, 'work')
        _require(owner in self.limits and category in self.limits[owner]['categories'] and
                 _dollar(amount_usd, 'amount_usd') > 0,
                 'unknown owner/category or zero reservation')
        with self._lock():
            rows, state = self._load()
            _require(not any(record['status'] == 'overrun' for record in state.values()),
                     'provider overrun freezes new paid dispatch')
            existing = state.get(attempt_id)
            if existing is not None:
                _require(existing['owner'] == owner and existing['category'] == category and
                         _dollar(existing['reserved_usd'], 'reserved_usd') ==
                         _dollar(amount_usd, 'amount_usd') and
                         existing['work_sha256'] == work_sha256,
                         'reservation ID collision')
                _require(existing['status'] == 'pending',
                         'attempt already dispatched or closed; reconcile before retry')
                return dict(existing)
            _require(not any(old['work_sha256'] == work_sha256 and
                             old['status'] != 'cancelled' for old in state.values()),
                     'same work already reserved or settled')
            record = {'schema': SCHEMA, 'kind': 'reserve',
                      'attempt_id': attempt_id, 'owner': owner,
                      'category': category, 'reserved_usd': amount_usd,
                      'work_sha256': work_sha256,
                      'previous': rows[-1]['hash']}
            projected = dict(state)
            projected[attempt_id] = {'owner': owner, 'category': category,
                                     'work_sha256': work_sha256,
                                     'reserved_usd': amount_usd,
                                     'actual_usd': None, 'status': 'pending',
                                     'evidence_sha256': None}
            self._check_caps(projected)
            self._append(record)
            return dict(projected[attempt_id])

    def mark_dispatched(self, attempt_id: str, request_sha256: str) -> dict:
        """Persist the exact request intent before sending it to any provider."""
        _hash(request_sha256, 'exact request')
        with self._lock():
            rows, state = self._load()
            record = state.get(attempt_id)
            _require(record is not None and record['status'] == 'pending',
                     'only a pending reservation can start dispatch')
            self._append({'schema': SCHEMA, 'kind': 'dispatch_started',
                          'attempt_id': attempt_id,
                          'request_sha256': request_sha256,
                          'previous': rows[-1]['hash']})
            return dict(self._load()[1][attempt_id])

    def mark_uncertain(self, attempt_id: str, failure_type: str) -> dict:
        with self._lock():
            rows, state = self._load()
            record = state.get(attempt_id)
            _require(record is not None, 'unknown reservation')
            if record['status'] == 'uncertain':
                _require(record['failure_type'] == failure_type,
                         'uncertain failure type changed')
                return dict(record)
            _require(record['status'] == 'dispatched' and failure_type in
                     {'provider', 'transport', 'environment', 'verifier'},
                     'only dispatched attempt can become uncertain')
            self._append({'schema': SCHEMA, 'kind': 'uncertain',
                          'attempt_id': attempt_id, 'failure_type': failure_type,
                          'previous': rows[-1]['hash']})
            return dict(self._load()[1][attempt_id])

    def settle(self, attempt_id: str, actual_usd: str,
               evidence_sha256: str) -> dict:
        _hash(evidence_sha256, 'usage evidence')
        actual = _dollar(actual_usd, 'actual_usd')
        with self._lock():
            rows, state = self._load()
            record = state.get(attempt_id)
            _require(record is not None, 'unknown reservation')
            if record['status'] == 'settled':
                _require(_dollar(record['actual_usd'], 'actual_usd') == actual and
                         record['evidence_sha256'] == evidence_sha256,
                         'settlement changed after confirmation')
                return dict(record)
            _require(record['status'] in ('dispatched', 'uncertain'),
                     'only dispatched or uncertain attempt can settle')
            kind = ('settle' if actual <=
                    _dollar(record['reserved_usd'], 'reserved_usd') else 'overrun')
            self._append({'schema': SCHEMA, 'kind': kind,
                          'attempt_id': attempt_id, 'actual_usd': actual_usd,
                          'evidence_sha256': evidence_sha256,
                          'previous': rows[-1]['hash']})
            return dict(self._load()[1][attempt_id])

    def cancel_with_no_charge(self, attempt_id: str,
                              no_charge_sha256: str) -> dict:
        _hash(no_charge_sha256, 'no-charge evidence')
        with self._lock():
            rows, state = self._load()
            record = state.get(attempt_id)
            _require(record is not None, 'unknown reservation')
            if record['status'] == 'cancelled':
                _require(record['evidence_sha256'] == no_charge_sha256,
                         'no-charge evidence changed')
                return dict(record)
            _require(record['status'] in ('pending', 'dispatched', 'uncertain'),
                     'only unresolved attempt can be cancelled')
            self._append({'schema': SCHEMA, 'kind': 'cancel',
                          'attempt_id': attempt_id,
                          'no_charge_sha256': no_charge_sha256,
                          'previous': rows[-1]['hash']})
            return dict(self._load()[1][attempt_id])

    def snapshot(self) -> dict:
        with self._lock():
            _, state = self._load()
            global_used, by_owner = self._totals(state)
            return {'schema': 'cua-full-study-budget-snapshot-v1',
                    'plan_sha256': self.plan_sha256,
                    'global_ceiling_usd': str(self.global_cap),
                    'global_reserved_or_spent_usd': str(global_used),
                    'owner_totals_usd': {owner: str(row['all_in'])
                                         for owner, row in by_owner.items()},
                    'pending_attempts': sum(row['status'] == 'pending'
                                             for row in state.values()),
                    'dispatched_attempts': sum(row['status'] == 'dispatched'
                                                for row in state.values()),
                    'uncertain_attempts': sum(row['status'] == 'uncertain'
                                               for row in state.values()),
                    'settled_attempts': sum(row['status'] == 'settled'
                                             for row in state.values()),
                    'provider_overrun_attempts': sum(row['status'] == 'overrun'
                                                      for row in state.values()),
                    'paid_dispatch_frozen': any(row['status'] == 'overrun'
                                                for row in state.values()),
                    'cancelled_attempts': sum(row['status'] == 'cancelled'
                                               for row in state.values())}
