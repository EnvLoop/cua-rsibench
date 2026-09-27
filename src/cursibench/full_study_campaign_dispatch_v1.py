"""Transactional, train/selection-only dispatcher for the frozen full study.

This module never prepares a cell or authorizes one. A caller must provide a
real six-cell pre-campaign manifest, its byte-identical prepared plan, the
six-cell v0.6.6 ratification, and an immutable public GitHub witness. The
current repository has none of those complete inputs and must fail closed.

Paid calls are separate transactions. A request and its full dollar/resource
reservation are durable before a provider is invoked. A crash or ambiguous
provider failure is not automatically replayed. The private journal contains
hashes and allowlisted metadata; request/response bodies remain private files.
"""

from __future__ import annotations

from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable
import urllib.request

from . import full_study_budget_v1 as dollars
from . import full_study_matrix_v1 as matrix
from . import full_study_pre_campaign_v1 as pre_campaign
from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-campaign-dispatch-v1'
WITNESS_SCHEMA = 'cua-full-study-public-pre-campaign-freeze-v1'
JOURNAL_SCHEMA = 'cua-full-study-campaign-journal-v1'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
PAID_KIND = re.compile(r'[a-z][a-z0-9_]{1,40}\Z')
PUBLIC_PATH = 'docs/evidence/full-study-pre-campaign-freeze.json'
MAX_PRIVATE_JSON_BYTES = 8_000_000
COUNTER_CAP_FIELDS = {
    'researcher_calls': 'researcher_calls_per_campaign',
    'teacher_rollout_calls': 'teacher_rollout_calls_per_campaign',
    'teacher_rollout_tokens': 'teacher_rollout_tokens_per_campaign',
    'candidate_submissions': 'candidate_submissions_per_campaign',
    'selection_evaluations': 'selection_evaluations_per_campaign',
}
RESOURCE_FIELDS = set(COUNTER_CAP_FIELDS) | {
    'e2b_sandbox_hours', 'e2b_peak_concurrency'}


class DispatchError(ValueError):
    """Safe subtype for locally detected study protocol failures."""


def _require(ok: bool, label: str) -> None:
    if not ok:
        raise DispatchError(label)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _json(path: Path, label: str) -> tuple[dict, bytes]:
    _require(path.is_file() and not path.is_symlink() and
             path.stat().st_size <= MAX_PRIVATE_JSON_BYTES,
             f'{label}_missing_or_unsafe')
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise DispatchError(f'{label}_invalid_json') from None
    _require(type(value) is dict, f'{label}_object_required')
    return value, raw


def _private_write_new(path: Path, raw: bytes) -> None:
    _require(not path.is_symlink(), 'private_output_symlink')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _fetch_immutable_witness(url: str, fetcher: Callable[[str], bytes] | None) -> bytes:
    if fetcher is not None:
        raw = fetcher(url)
    else:
        request = urllib.request.Request(url, headers={
            'User-Agent': 'EnvLoop-full-study-freeze-check/1.0'})
        with urllib.request.urlopen(request, timeout=20) as response:
            _require(response.url == url, 'public_witness_redirected')
            raw = response.read(MAX_PRIVATE_JSON_BYTES + 1)
    _require(type(raw) is bytes and 0 < len(raw) <= MAX_PRIVATE_JSON_BYTES,
             'public_witness_size_invalid')
    return raw


class FrozenStudy:
    """Rebuild every admission before creating any campaign/provider state."""

    def __init__(self, *, repo_root: Path, manifest_path: Path,
                 prepared_dir: Path, ratification_path: Path,
                 public_commit_sha1: str,
                 witness_fetcher: Callable[[str], bytes] | None = None):
        self.repo_root = Path(repo_root).resolve()
        self.manifest_path = Path(manifest_path).resolve()
        self.prepared_dir = Path(prepared_dir).resolve()
        self.ratification_path = Path(ratification_path).resolve()
        _require(bool(HEX40.fullmatch(public_commit_sha1)),
                 'immutable_public_commit_required')
        manifest, manifest_raw = _json(self.manifest_path, 'pre_campaign_manifest')
        self.manifest = manifest
        self.manifest_sha256 = _sha(manifest_raw)
        # This call traverses all 600 per-task qualification receipts and all
        # config/source/runtime references; a candidate inventory cannot pass.
        self.plan = pre_campaign.build(manifest, self.manifest_path.parent,
                                       self.manifest_sha256)
        self.plan_raw = cell_final.json_bytes(self.plan)
        self.plan_sha256 = _sha(self.plan_raw)
        plan_path = self.prepared_dir / 'campaign-plan.json'
        intent_path = self.prepared_dir / 'intent.json'
        _require(plan_path.is_file() and not plan_path.is_symlink() and
                 plan_path.read_bytes() == self.plan_raw,
                 'prepared_campaign_plan_changed_or_missing')
        intent, _ = _json(intent_path, 'prepared_intent')
        expected_intent = {
            'schema': pre_campaign.INTENT_SCHEMA,
            'study_id': self.plan['study_id'],
            'protocol_manifest_sha256': self.manifest_sha256,
            'plan_sha256': self.plan_sha256,
            'campaign_intent_sha256': [row['intent_sha256']
                                       for row in self.plan['campaign_intents']],
            'provider_dispatch_enabled': False,
            'scores_present': False,
        }
        _require(intent == expected_intent,
                 'prepared_campaign_intent_changed_or_missing')
        # The Desktop freeze validator checks the five actual local common
        # source bytes and requires six adapter profiles. No receipt is shipped.
        from native_desktop_factory.v066_final_freeze import validate_ratification
        self.ratification, self.ratification_sha256 = validate_ratification(
            self.ratification_path)
        self.public_commit_sha1 = public_commit_sha1
        url = ('https://raw.githubusercontent.com/EnvLoop/cua-rsibench/' +
               public_commit_sha1 + '/' + PUBLIC_PATH)
        witness_raw = _fetch_immutable_witness(url, witness_fetcher)
        try:
            witness = json.loads(witness_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DispatchError('public_witness_invalid_json') from None
        expected_action_bindings = {
            row['cell_id']: row['matched_bindings']['action_contract']
            for row in self.plan['cells']}
        _require(witness == {
            'schema': WITNESS_SCHEMA,
            'status': 'frozen_before_campaign_dispatch',
            'study_id': self.plan['study_id'],
            'protocol_manifest_sha256': self.manifest_sha256,
            'campaign_plan_sha256': self.plan_sha256,
            'ratification_sha256': self.ratification_sha256,
            'action_contract_sha256_by_cell': expected_action_bindings,
            'campaign_count': 24,
            'admitted_final_task_identities': 600,
            'hidden_final_model_attempts_before_freeze': 0,
        }, 'public_witness_does_not_bind_real_six_cell_freeze')
        self.public_witness_sha256 = _sha(witness_raw)
        self.public_witness_url = url
        self.intents = {(row['cell_id'], row['researcher_id']): row
                        for row in self.plan['campaign_intents']}
        _require(len(self.intents) == 24, 'campaign_intents_not_unique')

    def task_views(self, cell_id: str) -> dict[str, tuple[dict, ...]]:
        """Only train and selection identities leave evaluator-owned state."""
        _require(cell_id in matrix.CELLS, 'unknown_cell')
        cell = next(row for row in self.manifest['cells']
                    if row['cell_id'] == cell_id)
        base = matrix._slot(self.manifest_path.parent, cell['base_manifest'],
                            cell_id=cell_id, researcher_id='shared-base',
                            role='base')
        return {'train': tuple(base['train']),
                'selection': tuple(base['selection'])}

    def open_campaign(self, private_dir: Path, *, cell_id: str,
                      researcher_id: str, now: Callable[[], float] = time.time):
        owner = (cell_id, researcher_id)
        _require(owner in self.intents, 'undeclared_campaign')
        work = self.repo_root / 'work'
        target = Path(private_dir).absolute()
        _require(not work.is_symlink() and not target.is_symlink() and
                 target.parent.resolve().is_relative_to(work.resolve()),
                 'private_work_directory_required')
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.chmod(0o700)
        budget = dollars.StudyBudgetLedger(work / 'full-study-budget.jsonl',
                                           self.plan)
        return CampaignSession(self, target, self.intents[owner], budget,
                               now=now)


class CampaignJournal:
    def __init__(self, path: Path, header: dict):
        self.path = path
        self.lock_path = path.with_name('.' + path.name + '.lock')
        self.header = header
        if not path.exists():
            _private_write_new(path, _canonical({
                **header, 'previous': None,
                'hash': _sha(_canonical({**header, 'previous': None}))}))
        self.rows()

    def _lock(self):
        class Lock:
            def __enter__(instance):
                _require(not self.lock_path.is_symlink(), 'journal_lock_symlink')
                descriptor = os.open(self.lock_path,
                                     os.O_WRONLY | os.O_CREAT, 0o600)
                instance.file = os.fdopen(descriptor, 'w')
                fcntl.flock(instance.file, fcntl.LOCK_EX)

            def __exit__(instance, *_):
                instance.file.close()
        return Lock()

    def rows(self) -> list[dict]:
        _require(self.path.is_file() and not self.path.is_symlink() and
                 self.path.stat().st_mode & 0o077 == 0,
                 'journal_private_file_required')
        try:
            rows = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DispatchError('journal_invalid_json') from None
        _require(bool(rows), 'journal_empty')
        previous = None
        for index, row in enumerate(rows):
            _require(type(row) is dict and row.get('previous') == previous,
                     'journal_hash_chain_broken')
            core = {key: value for key, value in row.items() if key != 'hash'}
            _require(row.get('hash') == _sha(_canonical(core)),
                     'journal_hash_chain_broken')
            if index == 0:
                _require(core == {**self.header, 'previous': None},
                         'journal_frozen_header_changed')
            else:
                _require(row.get('sequence') == index and
                         row.get('schema') == JOURNAL_SCHEMA and
                         row.get('kind') != 'header',
                         'journal_event_sequence_invalid')
            previous = row['hash']
        return rows

    def append(self, kind: str, data: dict) -> dict:
        _require(bool(PAID_KIND.fullmatch(kind)) and type(data) is dict,
                 'journal_event_invalid')
        with self._lock():
            rows = self.rows()
            core = {'schema': JOURNAL_SCHEMA, 'kind': kind,
                    'sequence': len(rows), 'data': data,
                    'previous': rows[-1]['hash']}
            row = {**core, 'hash': _sha(_canonical(core))}
            descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(descriptor, 'ab') as stream:
                stream.write(_canonical(row))
                stream.flush()
                os.fsync(stream.fileno())
            return row


class CampaignSession:
    def __init__(self, study: FrozenStudy, directory: Path, intent: dict,
                 budget: dollars.StudyBudgetLedger, *,
                 now: Callable[[], float] = time.time):
        self.study, self.directory, self.intent = study, directory, intent
        self.budget, self.now = budget, now
        self.owner = f"{intent['cell_id']}:{intent['researcher_id']}"
        self.views = study.task_views(intent['cell_id'])
        header = {'schema': JOURNAL_SCHEMA, 'kind': 'header',
                  'plan_sha256': study.plan_sha256,
                  'intent_sha256': intent['intent_sha256'],
                  'ratification_sha256': study.ratification_sha256,
                  'public_witness_sha256': study.public_witness_sha256,
                  'owner': self.owner}
        self.journal = CampaignJournal(directory / 'campaign.jsonl', header)
        if len(self.journal.rows()) == 1:
            self.journal.append('campaign_started',
                                {'epoch_seconds': int(self.now())})
        self._check_time()

    def _events(self, kind: str | None = None) -> list[dict]:
        rows = self.journal.rows()[1:]
        return [row for row in rows if kind is None or row['kind'] == kind]

    def _check_time(self) -> None:
        starts = self._events('campaign_started')
        _require(len(starts) == 1, 'campaign_start_missing_or_repeated')
        started = starts[0]['data']['epoch_seconds']
        _require(type(started) is int and started > 0 and
                 0 <= self.now() - started <= matrix.CAMPAIGN_HOURS * 3600,
                 'campaign_sixteen_hour_limit')

    def _counter_totals(self) -> dict[str, Decimal]:
        totals = {key: Decimal(0) for key in COUNTER_CAP_FIELDS}
        totals['e2b_sandbox_hours'] = Decimal(0)
        totals['e2b_peak_concurrency'] = Decimal(0)
        for event in self._events('paid_intent'):
            for name, value in event['data']['resource_reservation'].items():
                if name == 'e2b_peak_concurrency':
                    totals[name] = max(totals[name], Decimal(value))
                else:
                    totals[name] += Decimal(value)
        return totals

    def _check_resources(self, category: str, reservation: dict) -> dict[str, str]:
        _require(type(reservation) is dict and
                 set(reservation) <= RESOURCE_FIELDS,
                 'resource_reservation_invalid')
        normalized = {}
        for name, value in reservation.items():
            _require(isinstance(value, str), 'resource_decimal_string_required')
            try:
                amount = Decimal(value)
            except Exception:
                raise DispatchError('resource_decimal_invalid') from None
            _require(amount.is_finite() and amount >= 0,
                     'resource_decimal_invalid')
            if name not in {'e2b_sandbox_hours'}:
                _require(amount == int(amount), 'resource_integer_required')
            normalized[name] = str(amount)
        if category == 'researcher_inference':
            _require(normalized == {'researcher_calls': '1'},
                     'researcher_call_counter_required')
        elif category == 'teacher_rollout':
            _require(set(normalized) == {'teacher_rollout_calls',
                                         'teacher_rollout_tokens'} and
                     normalized['teacher_rollout_calls'] == '1' and
                     Decimal(normalized['teacher_rollout_tokens']) > 0,
                     'teacher_call_and_token_counter_required')
        elif category == 'e2b':
            _require(set(normalized) == {'e2b_sandbox_hours',
                                         'e2b_peak_concurrency'} and
                     Decimal(normalized['e2b_sandbox_hours']) > 0 and
                     Decimal(normalized['e2b_peak_concurrency']) > 0,
                     'e2b_hours_and_concurrency_required')
        elif category == 'tinker':
            _require(not normalized, 'tinker_resource_counter_must_be_metered_separately')
        elif category == 'storage_application':
            _require(not normalized, 'storage_application_has_no_count_counter')
        totals = self._counter_totals()
        caps = self.intent['matched_count_caps']
        for name, amount in normalized.items():
            cap = (self.intent['e2b_sandbox_hours_cap'] if name ==
                   'e2b_sandbox_hours' else caps['e2b_peak_concurrency'] if name ==
                   'e2b_peak_concurrency' else caps[COUNTER_CAP_FIELDS[name]])
            projected = (max(totals[name], Decimal(amount)) if name ==
                         'e2b_peak_concurrency' else totals[name] + Decimal(amount))
            _require(projected <= Decimal(str(cap)),
                     f'{name}_cap_exhausted')
        return normalized

    def _unresolved_failure(self) -> bool:
        failures = {row['data']['attempt_id'] for row in
                    self._events('paid_uncertain')}
        reconciled = {row['data']['attempt_id'] for row in
                      self._events('paid_reconciled')}
        return bool(failures - reconciled)

    def _inflight_attempts(self) -> set[str]:
        intents = {row['data']['attempt_id'] for row in
                   self._events('paid_intent')}
        completed = {row['data']['attempt_id'] for row in
                     self._events('paid_result') + self._events('paid_uncertain')}
        return intents - completed

    def _orphan_budget_attempts(self) -> set[str]:
        journaled = {row['data']['attempt_id'] for row in
                     self._events('paid_intent') +
                     self._events('orphan_reconciled')}
        return set(self.budget.owner_attempts(self.owner)) - journaled

    def dispatch_paid(self, *, attempt_id: str, category: str,
                      work: object, request: object, reserve_usd: str,
                      resource_reservation: dict[str, str],
                      provider: Callable[[object], object]) -> dict:
        """Commit the exact request before invoking one provider callback.

        The callback is invoked at most once by this method. On interruption,
        the existing intent/dispatched dollar reservation blocks replay. The
        caller must reconcile actual provider usage independently.
        """
        self._check_time()
        _require(not self._events('selection_frozen') and
                 not self._unresolved_failure() and
                 not self._inflight_attempts() and
                 not self._orphan_budget_attempts(),
                 'campaign_frozen_or_paid_call_unreconciled')
        _require(category in dollars.CAMPAIGN_CATEGORIES and
                 category != 'selected_final' and
                 type(attempt_id) is str and
                 dollars.ATTEMPT.fullmatch(attempt_id) is not None and
                 callable(provider), 'paid_dispatch_contract_invalid')
        _require(not any(row['data']['attempt_id'] == attempt_id for row in
                         self._events('paid_intent')),
                 'attempt_already_recorded_no_automatic_replay')
        units = self._check_resources(category, resource_reservation)
        request_raw = _canonical(request)
        _require(len(request_raw) <= MAX_PRIVATE_JSON_BYTES,
                 'paid_request_too_large')
        work_sha = _sha(_canonical({'owner': self.owner,
                                    'category': category, 'work': work}))
        _require(not any(row['data']['work_sha256'] == work_sha for row in
                         self._events('paid_intent')),
                 'same_work_already_recorded_no_automatic_replay')
        request_sha = _sha(request_raw)
        request_path = self.directory / f'{attempt_id}.request.private.json'
        result_path = self.directory / f'{attempt_id}.result.private.json'
        _require(not request_path.exists() and not result_path.exists(),
                 'unowned_attempt_artifact_exists')
        self.budget.reserve(attempt_id, self.owner, category,
                            reserve_usd, work_sha)
        _private_write_new(request_path, request_raw)
        self.journal.append('paid_intent', {
            'attempt_id': attempt_id, 'category': category,
            'work_sha256': work_sha, 'request_sha256': request_sha,
            'reserved_usd': reserve_usd,
            'resource_reservation': units,
            'epoch_seconds': int(self.now()),
        })
        self.budget.mark_dispatched(attempt_id, request_sha)
        try:
            result = provider(request)
            result_raw = _canonical(result)
            _require(len(result_raw) <= MAX_PRIVATE_JSON_BYTES,
                     'paid_result_too_large')
            _private_write_new(result_path, result_raw)
            self.journal.append('paid_result', {
                'attempt_id': attempt_id,
                'result_sha256': _sha(result_raw),
                'epoch_seconds': int(self.now()),
            })
            return {'attempt_id': attempt_id, 'result': result,
                    'result_sha256': _sha(result_raw),
                    'billing_state': 'awaiting_provider_usage_reconciliation'}
        except Exception as exc:
            failure_type = ('provider' if type(exc).__name__ in
                            {'ProviderFailure', 'APIStatusError'} else 'transport')
            self.budget.mark_uncertain(attempt_id, failure_type)
            self.journal.append('paid_uncertain', {
                'attempt_id': attempt_id, 'failure_type': failure_type,
                'exception_type': type(exc).__name__,
                'epoch_seconds': int(self.now()),
            })
            raise DispatchError('paid_response_uncertain_reconcile_before_retry') from None

    def reconcile_paid(self, attempt_id: str, *, actual_usd: str | None,
                       provider_usage_sha256: str | None = None,
                       provider_no_charge_sha256: str | None = None) -> dict:
        _require(any(row['data']['attempt_id'] == attempt_id for row in
                     self._events('paid_intent')) and
                 not any(row['data']['attempt_id'] == attempt_id for row in
                         self._events('paid_reconciled')),
                 'unknown_or_already_reconciled_attempt')
        if actual_usd is None:
            _require(cell_final.is_hash(provider_no_charge_sha256) and
                     provider_usage_sha256 is None,
                     'trusted_no_charge_receipt_required')
            record = self.budget.cancel_with_no_charge(
                attempt_id, provider_no_charge_sha256)
            evidence = provider_no_charge_sha256
        else:
            _require(cell_final.is_hash(provider_usage_sha256) and
                     provider_no_charge_sha256 is None,
                     'trusted_provider_usage_receipt_required')
            record = self.budget.settle(attempt_id, actual_usd,
                                        provider_usage_sha256)
            evidence = provider_usage_sha256
        self.journal.append('paid_reconciled', {
            'attempt_id': attempt_id, 'status': record['status'],
            'actual_usd': actual_usd,
            'evidence_sha256': evidence,
            'epoch_seconds': int(self.now()),
        })
        return record

    def reconcile_orphan_reservation(self, attempt_id: str, *,
                                     provider_no_charge_sha256: str) -> dict:
        """Close a pre-journal crash only with an independently checked no-charge proof."""
        _require(attempt_id in self._orphan_budget_attempts() and
                 cell_final.is_hash(provider_no_charge_sha256),
                 'orphan_no_charge_evidence_required')
        record = self.budget.cancel_with_no_charge(attempt_id,
                                                   provider_no_charge_sha256)
        self.journal.append('orphan_reconciled', {
            'attempt_id': attempt_id, 'status': record['status'],
            'no_charge_sha256': provider_no_charge_sha256,
            'epoch_seconds': int(self.now()),
        })
        return record

    def snapshot(self) -> dict:
        events = self._events()
        counters = self._counter_totals()
        return {'schema': SCHEMA, 'owner': self.owner,
                'plan_sha256': self.study.plan_sha256,
                'public_witness_sha256': self.study.public_witness_sha256,
                'campaign_started_at': self._events('campaign_started')[0]['data']['epoch_seconds'],
                'paid_attempt_count': len(self._events('paid_intent')),
                'provider_result_count': len(self._events('paid_result')),
                'uncertain_unreconciled': self._unresolved_failure(),
                'inflight_unresolved_attempts': sorted(self._inflight_attempts()),
                'orphan_budget_attempts': sorted(self._orphan_budget_attempts()),
                'resource_reserved': {key: str(value)
                                      for key, value in counters.items()},
                'selection_frozen': bool(self._events('selection_frozen')),
                'journal_head_sha256': events[-1]['hash'] if events else
                    self.journal.rows()[0]['hash']}
