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
from decimal import ROUND_CEILING
from contextlib import contextmanager
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
from . import full_study_selection_environment_v1 as selection_environment
from . import full_study_selection_paid_coverage_v1 as paid_coverage
from . import scale_final_v06 as cell_final


SCHEMA = 'cua-full-study-campaign-dispatch-v1'
WITNESS_SCHEMA = 'cua-full-study-public-pre-campaign-freeze-v1'
JOURNAL_SCHEMA = 'cua-full-study-campaign-journal-v1'
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
PAID_KIND = re.compile(r'[a-z][a-z0-9_]{1,40}\Z')
PUBLIC_PATH = 'docs/evidence/full-study-pre-campaign-freeze.json'
MAX_PRIVATE_JSON_BYTES = 8_000_000
TINKER_MODEL = 'Qwen/Qwen3.8-27B'
TINKER_PATH = re.compile(r'tinker://[^\s/]+/sampler_weights/[^\s/]+\Z')
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


def _private_input(path: Path, repo_root: Path, label: str) -> Path:
    original = Path(path)
    _require(not original.is_symlink(), f'{label}_private_work_file_required')
    target = original.resolve()
    _require(target.is_file() and
             target.is_relative_to(repo_root / 'work') and
             target.stat().st_mode & 0o077 == 0,
             f'{label}_private_work_file_required')
    return target


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

    def researcher_configuration(self, researcher_id: str) -> dict:
        _require(researcher_id in matrix.RESEARCHERS, 'unknown_researcher')
        reference = self.manifest['configurations']['researchers'][researcher_id]
        path, raw = cell_final.evidence_file(
            self.manifest_path.parent, reference, 'researcher configuration')
        config = json.loads(raw)
        _require(config['model'] == matrix.RESEARCHERS[researcher_id] and
                 _sha(raw) == self.plan['configuration_bindings']
                 ['researchers'][researcher_id]['config_sha256'],
                 'researcher_configuration_drift')
        assets = {}
        for name in ('prompt', 'harness', 'tool_grammar', 'decoding',
                     'provider_route'):
            _, data = cell_final.evidence_file(
                path.parent, config['assets'][name], f'researcher/{name}')
            assets[name] = data
        return {'settings': config['settings'], 'model': config['model'],
                'snapshot_id': config['snapshot_id'],
                'config_sha256': _sha(raw), 'assets': assets}

    def teacher_configuration(self) -> dict:
        reference = self.manifest['configurations']['teacher']
        path, raw = cell_final.evidence_file(
            self.manifest_path.parent, reference, 'teacher configuration')
        config = json.loads(raw)
        _require(config['model'] == matrix.TEACHER and
                 _sha(raw) == self.plan['configuration_bindings']
                 ['teacher']['config_sha256'],
                 'teacher_configuration_drift')
        assets = {}
        for name in ('prompt', 'harness', 'tool_grammar', 'decoding',
                     'provider_route'):
            _, data = cell_final.evidence_file(
                path.parent, config['assets'][name], f'teacher/{name}')
            assets[name] = data
        return {'settings': config['settings'], 'model': config['model'],
                'snapshot_id': config['snapshot_id'],
                'config_sha256': _sha(raw), 'assets': assets}

    def student_training_configuration(self) -> tuple[dict, str]:
        reference = self.manifest['configurations']['student']
        config_path, raw = cell_final.evidence_file(
            self.manifest_path.parent, reference, 'student configuration')
        config = json.loads(raw)
        _require(config['model'] == TINKER_MODEL and
                 _sha(raw) == self.plan['configuration_bindings']
                 ['student']['config_sha256'],
                 'student_training_configuration_drift')
        _, data = cell_final.evidence_file(
            config_path.parent, config['assets']['training'],
            'student training asset')
        try:
            training = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DispatchError('frozen_qwen_training_asset_not_json') from None
        needed = {'schema', 'model', 'action_profile', 'lora_rank', 'seed',
                  'batch_size', 'optimizer_steps', 'learning_rate',
                  'max_supervised_tokens', 'max_scheduled_tokens',
                  'sample_max_tokens', 'train_usd_per_million_tokens',
                  'prefill_usd_per_million_tokens',
                  'sample_usd_per_million_tokens',
                  'billing_multiplier_upper'}
        _require(type(training) is dict and set(training) == needed and
                 training['schema'] == 'cua-full-study-qwen-sft-training-v1' and
                 training['model'] == TINKER_MODEL and
                 training['action_profile'] == 'scale-action-profile-v0.6.6',
                 'frozen_qwen_training_asset_invalid')
        for name, maximum in (('lora_rank', 256), ('batch_size', 128),
                              ('optimizer_steps', 10000),
                              ('max_supervised_tokens', 32768),
                              ('max_scheduled_tokens', 100_000_000),
                              ('sample_max_tokens', 4096)):
            _require(type(training[name]) is int and
                     0 < training[name] <= maximum,
                     'frozen_qwen_training_asset_invalid')
        _require(type(training['seed']) is int and
                 0 <= training['seed'] < 2**31 and
                 training['batch_size'] * training['optimizer_steps'] <=
                 training['max_scheduled_tokens'],
                 'frozen_qwen_training_asset_invalid')
        for name in ('learning_rate', 'train_usd_per_million_tokens',
                     'prefill_usd_per_million_tokens',
                     'sample_usd_per_million_tokens',
                     'billing_multiplier_upper'):
            _require(type(training[name]) is str,
                     'frozen_qwen_training_asset_invalid')
            try:
                amount = Decimal(training[name])
            except Exception:
                raise DispatchError('frozen_qwen_training_asset_invalid') from None
            _require(amount.is_finite() and amount > 0 and
                     (name != 'billing_multiplier_upper' or amount >= 1),
                     'frozen_qwen_training_asset_invalid')
        return training, _sha(data)

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
        # Expired campaigns remain readable for reconciliation and audit.
        self._audit_paid_files()

    def _events(self, kind: str | None = None) -> list[dict]:
        rows = self.journal.rows()[1:]
        return [row for row in rows if kind is None or row['kind'] == kind]

    @contextmanager
    def _operation_lock(self):
        path = self.directory / '.campaign-operation.lock'
        _require(not path.is_symlink(), 'campaign_operation_lock_symlink')
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

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
        totals['selection_evaluations'] += len(self._events('selection_started'))
        return totals

    def _check_resources(self, category: str, reservation: dict,
                         request: object) -> dict[str, str]:
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
            request_schema = (request.get('schema') if type(request) is dict
                              else None)
            if request_schema == 'cua-full-study-tinker-sft-request-v1':
                _require(normalized == {'candidate_submissions': '1'},
                         'tinker_candidate_submission_counter_required')
            elif request_schema == 'cua-full-study-selection-sampling-request-v1':
                _require(not normalized,
                         'selection_sampler_cannot_submit_training_candidate')
            else:
                raise DispatchError('tinker_request_schema_unbound')
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

    def _audit_paid_files(self) -> None:
        state = self.budget.owner_attempts(self.owner)
        intents = self._events('paid_intent')
        results = self._events('paid_result')
        _require(len({row['data']['attempt_id'] for row in intents}) ==
                 len(intents) and
                 len({row['data']['attempt_id'] for row in results}) ==
                 len(results), 'paid_attempt_event_repeated')
        for row in intents:
            info = row['data']
            attempt_id = info['attempt_id']
            record = state.get(attempt_id)
            _require(record is not None and
                     record['category'] == info['category'] and
                     record['work_sha256'] == info['work_sha256'] and
                     Decimal(record['reserved_usd']) ==
                     Decimal(info['reserved_usd']),
                     'paid_intent_differs_from_budget_ledger')
            request_path = (self.directory /
                            f'{attempt_id}.request.private.json')
            _require(request_path.is_file() and
                     not request_path.is_symlink() and
                     request_path.stat().st_mode & 0o077 == 0 and
                     _sha(request_path.read_bytes()) == info['request_sha256'],
                     'paid_request_bytes_changed_or_missing')
            if record['status'] != 'pending':
                _require(record.get('request_sha256') ==
                         info['request_sha256'],
                         'paid_request_hash_differs_from_budget_ledger')
        for row in results:
            info = row['data']
            _require(info['attempt_id'] in state,
                     'paid_result_missing_budget_attempt')
            result_path = (self.directory /
                           f"{info['attempt_id']}.result.private.json")
            _require(result_path.is_file() and
                     not result_path.is_symlink() and
                     result_path.stat().st_mode & 0o077 == 0 and
                     _sha(result_path.read_bytes()) == info['result_sha256'],
                     'paid_result_bytes_changed_or_missing')

    def _selection_result(self, result: object, *, checkpoint_sha256: str) -> dict:
        _require(type(result) is dict and set(result) == {
            'schema', 'cell_id', 'checkpoint_sha256', 'evaluator_isolated',
            'tasks'}, 'selection_result_shape_invalid')
        _require(result['schema'] == 'cua-full-study-selection-saved-result-v1' and
                 result['cell_id'] == self.intent['cell_id'] and
                 result['checkpoint_sha256'] == checkpoint_sha256 and
                 result['evaluator_isolated'] is True and
                 type(result['tasks']) is list and
                 len(result['tasks']) == matrix.SELECTION_PER_CELL,
                 'selection_result_binding_invalid')
        expected = {row['task_id']: row['package_sha256']
                    for row in self.views['selection']}
        scores = {}
        for row in result['tasks']:
            _require(type(row) is dict and set(row) == {
                'task_id', 'package_sha256', 'score', 'saved_state_sha256',
                'verifier_receipt_sha256', 'reset_receipt_sha256'},
                'selection_task_result_shape_invalid')
            task_id = row['task_id']
            _require(task_id in expected and task_id not in scores and
                     row['package_sha256'] == expected[task_id] and
                     type(row['score']) is int and row['score'] in (0, 1) and
                     all(cell_final.is_hash(row[name]) for name in (
                         'saved_state_sha256', 'verifier_receipt_sha256',
                         'reset_receipt_sha256')),
                     'selection_result_contains_unbound_or_unscored_task')
            scores[task_id] = row['score']
        _require(set(scores) == set(expected), 'selection_task_coverage_incomplete')
        return scores

    def record_base_selection(self, result: dict) -> dict:
        """Import evaluator-owned 20-task base feedback; never a final task."""
        self._check_time()
        _require(not self._events('base_selection') and
                 not self._events('researcher_proposal'),
                 'base_selection_already_recorded_or_research_started')
        scores = self._selection_result(
            result, checkpoint_sha256=self.intent['base_checkpoint_sha256'])
        raw = _canonical(result)
        _private_write_new(self.directory / 'base-selection.private.json', raw)
        self.journal.append('base_selection', {
            'result_sha256': _sha(raw), 'wins': sum(scores.values()),
            'epoch_seconds': int(self.now()),
        })
        return {'wins': sum(scores.values()), 'task_count': len(scores),
                'result_sha256': _sha(raw)}

    def _train_context(self, path: Path) -> tuple[list[dict], str]:
        target = _private_input(path, self.study.repo_root, 'train_context')
        value, raw = _json(target, 'train_context')
        _require(set(value) == {'schema', 'cell_id', 'tasks'} and
                 value['schema'] == 'cua-full-study-researcher-train-view-v1' and
                 value['cell_id'] == self.intent['cell_id'] and
                 type(value['tasks']) is list and
                 len(value['tasks']) == len(self.views['train']),
                 'train_context_shape_or_cell_invalid')
        expected = {row['task_id']: row['package_sha256']
                    for row in self.views['train']}
        seen = set()
        for row in value['tasks']:
            _require(type(row) is dict and set(row) == {
                'task_id', 'package_sha256', 'visible_instruction'},
                'train_context_task_shape_invalid')
            task_id = row['task_id']
            _require(task_id in expected and task_id not in seen and
                     row['package_sha256'] == expected[task_id] and
                     type(row['visible_instruction']) is str and
                     1 <= len(row['visible_instruction'].encode()) <= 8192,
                     'train_context_has_unbound_or_oversized_task')
            seen.add(task_id)
        _require(seen == set(expected), 'train_context_coverage_incomplete')
        return value['tasks'], _sha(raw)

    def _selection_feedback(self) -> list[dict]:
        base = self.directory / 'base-selection.private.json'
        result, raw = _json(base, 'base_selection')
        events = self._events('base_selection')
        _require(len(events) == 1 and
                 events[0]['data']['result_sha256'] == _sha(raw),
                 'base_selection_receipt_changed')
        self._selection_result(
            result, checkpoint_sha256=self.intent['base_checkpoint_sha256'])
        feedback = [{'round_index': 0, 'role': 'shared_base',
                     'score_wins': sum(row['score'] for row in result['tasks']),
                     'tasks': [{'task_id': row['task_id'],
                                'score': row['score']}
                               for row in result['tasks']]}]
        for event in self._events('selection_scored'):
            self._verify_selection_coverage_event(event)
            selection, selection_raw = _json(
                self.directory /
                f"selection-{event['data']['attempt_id']}.private.json",
                'prior_selection')
            _require(_sha(selection_raw) == event['data']['result_sha256'],
                     'prior_selection_receipt_changed')
            self._selection_result(
                selection,
                checkpoint_sha256=event['data']['checkpoint_path_sha256'])
            feedback.append({
                'round_index': event['data']['round_index'],
                'role': 'candidate',
                'score_wins': event['data']['score_wins'],
                'promoted': event['data']['promoted'],
                'regressions_vs_incumbent': event['data']
                ['regressions_vs_incumbent'],
                'tasks': [{'task_id': row['task_id'],
                           'score': row['score']}
                          for row in selection['tasks']],
            })
        return feedback

    def _research_history(self) -> list[dict]:
        history = []
        scored = {row['data']['round_index']: row['data']
                  for row in self._events('selection_scored')}
        for event in self._events('researcher_proposal')[-4:]:
            round_index = event['data']['round_index']
            proposal, raw = _json(
                self.directory / f'proposal-{round_index:03d}.private.json',
                'prior_researcher_proposal')
            _require(_sha(raw) == event['data']['proposal_sha256'],
                     'prior_researcher_proposal_changed')
            outcome = scored.get(round_index)
            history.append({
                'round_index': round_index,
                'hypothesis_excerpt': proposal['hypothesis'][:1024],
                'hypothesis_sha256': event['data']['hypothesis_sha256'],
                'train_task_ids': proposal['train_task_ids'],
                'selection_wins': outcome['score_wins'] if outcome else None,
                'promoted': outcome['promoted'] if outcome else None,
            })
        return history

    def _researcher_quote(self, config: dict, prompt: str) -> str:
        try:
            rate = json.loads(config['assets']['provider_route'])
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise DispatchError('frozen_researcher_rate_card_missing') from None
        _require(type(rate) is dict and set(rate) == {
            'schema', 'model', 'base_url', 'input_usd_per_million_tokens',
            'output_usd_per_million_tokens', 'fixed_usd_per_call',
            'billing_multiplier_upper'},
            'frozen_researcher_rate_card_invalid')
        _require(rate['schema'] == 'cua-agentrouterhub-rate-upper-v1' and
                 rate['model'] == config['model'] and
                 rate['base_url'] == 'https://sub2api.agentrouterhub.com' and
                 os.environ.get('OPENAI_BASE_URL', rate['base_url']).rstrip('/') ==
                 rate['base_url'], 'frozen_researcher_route_mismatch')
        input_bytes = len(prompt.encode())
        _require(0 < input_bytes <= 65_536, 'researcher_prompt_byte_limit')
        try:
            input_rate = Decimal(rate['input_usd_per_million_tokens'])
            output_rate = Decimal(rate['output_usd_per_million_tokens'])
            fixed = Decimal(rate['fixed_usd_per_call'])
            multiplier = Decimal(rate['billing_multiplier_upper'])
        except Exception:
            raise DispatchError('frozen_researcher_rate_card_invalid') from None
        _require(all(value.is_finite() and value >= 0 for value in
                     (input_rate, output_rate, fixed)) and
                 multiplier.is_finite() and multiplier >= 1 and
                 input_rate > 0 and output_rate > 0,
                 'frozen_researcher_rate_card_invalid')
        output_bound = config['settings']['max_output_tokens']
        # A deliberately conservative text-only upper envelope: UTF-8 bytes
        # plus 2,048 provider framing tokens, then the frozen account markup.
        amount = (fixed + (Decimal(input_bytes + 2048) * input_rate +
                           Decimal(output_bound) * output_rate) /
                  Decimal(1_000_000)) * multiplier
        return str(amount.quantize(Decimal('0.000000001'),
                                   rounding=ROUND_CEILING))

    def quote_responses_upper(self, config: dict, prompt: str) -> str:
        """Frozen AgentRouterHub text-call upper envelope for either role."""
        return self._researcher_quote(config, prompt)

    def dispatch_researcher(self, *, round_index: int, train_context_path: Path,
                            provider: Callable[[str, dict], tuple[str, dict]] | None = None) -> dict:
        """One real Responses request, or one fake-provider test request.

        The provider receives no official-final identity, package, instruction,
        or gold. Invalid model JSON spends its call but cannot create a dataset.
        """
        self._check_time()
        _require(type(round_index) is int and round_index > 0 and
                 round_index <= self.intent['matched_count_caps']
                 ['candidate_submissions_per_campaign'] and
                 len(self._events('base_selection')) == 1 and
                 not self._events('selection_frozen'),
                 'researcher_round_or_baseline_invalid')
        _require(round_index == len(self._events('researcher_proposal')) +
                 len(self._events('researcher_invalid_output')) + 1,
                 'researcher_round_not_sequential')
        config = self.study.researcher_configuration(
            self.intent['researcher_id'])
        train_tasks, context_sha = self._train_context(train_context_path)
        feedback = self._selection_feedback()
        history = self._research_history()
        prompt = (config['assets']['prompt'].decode('utf-8') + '\n' +
                  json.dumps({
                      'schema': 'cua-full-study-researcher-input-v1',
                      'cell_id': self.intent['cell_id'],
                      'round_index': round_index,
                      'train_tasks': train_tasks,
                      'selection_feedback': feedback,
                      'research_history': history,
                      'instruction': ('Propose one training-data hypothesis using '
                                      'only the listed train tasks. Return a JSON '
                                      'object with schema, hypothesis, '
                                      'train_task_ids, and teacher_request. '
                                      'Never request final task content.'),
                  }, sort_keys=True, ensure_ascii=False,
                     separators=(',', ':')))
        quote = self._researcher_quote(config, prompt)
        settings = config['settings']
        attempt_id = f'researcher-{round_index:03d}'
        request = {'prompt': prompt, 'model': config['model'],
                   'max_output_tokens': settings['max_output_tokens'],
                   'reasoning_effort': settings['reasoning_effort'],
                   'reasoning_mode': settings['reasoning_mode']}
        if provider is None:
            from .agentrouter import response_receipt
            def provider(text, frozen):
                return response_receipt(
                    text, model=frozen['model'],
                    max_output_tokens=frozen['max_output_tokens'],
                    timeout=180,
                    reasoning_effort=frozen['reasoning_effort'],
                    reasoning_mode=frozen['reasoning_mode'])
        def call(_request):
            text, receipt = provider(prompt, request)
            usage = receipt.get('usage') if type(receipt) is dict else None
            _require(type(text) is str and 0 < len(text.encode()) <= 131_072 and
                     type(receipt) is dict and
                     receipt.get('reported_model') == config['model'] and
                     receipt.get('status') == 'completed' and
                     type(usage) is dict and
                     type(usage.get('input_tokens')) is int and
                     0 <= usage['input_tokens'] <=
                     len(prompt.encode()) + 2048 and
                     type(usage.get('output_tokens')) is int and
                     0 <= usage['output_tokens'] <=
                     settings['max_output_tokens'],
                     'researcher_provider_model_or_body_invalid')
            return {'text': text, 'receipt': receipt}
        paid = self.dispatch_paid(
            attempt_id=attempt_id, category='researcher_inference',
            work={'round_index': round_index,
                  'train_context_sha256': context_sha,
                  'base_selection_sha256': self._events('base_selection')[0]
                  ['data']['result_sha256'],
                  'configuration_sha256': config['config_sha256']},
            request=request, reserve_usd=quote,
            resource_reservation={'researcher_calls': '1'}, provider=call)
        raw = paid['result']['text']
        try:
            proposal = json.loads(raw)
            _require(type(proposal) is dict and set(proposal) == {
                'schema', 'hypothesis', 'train_task_ids', 'teacher_request'} and
                proposal['schema'] == 'cua-full-study-researcher-proposal-v1' and
                type(proposal['hypothesis']) is str and
                1 <= len(proposal['hypothesis'].encode()) <= 8192 and
                type(proposal['teacher_request']) is str and
                1 <= len(proposal['teacher_request'].encode()) <= 8192 and
                type(proposal['train_task_ids']) is list and
                proposal['train_task_ids'] and
                len(proposal['train_task_ids']) == len(set(proposal['train_task_ids'])) and
                set(proposal['train_task_ids']) <= {
                    row['task_id'] for row in self.views['train']},
                'researcher_proposal_not_train_only')
        except (DispatchError, TypeError, ValueError, json.JSONDecodeError):
            self.journal.append('researcher_invalid_output', {
                'round_index': round_index,
                'paid_attempt_id': attempt_id,
                'model_text_sha256': _sha(raw.encode()),
                'epoch_seconds': int(self.now()),
            })
            raise DispatchError('researcher_output_invalid_call_preserved') from None
        proposal_raw = _canonical(proposal)
        _private_write_new(self.directory /
                           f'proposal-{round_index:03d}.private.json',
                           proposal_raw)
        self.journal.append('researcher_proposal', {
            'round_index': round_index, 'paid_attempt_id': attempt_id,
            'train_context_sha256': context_sha,
            'proposal_sha256': _sha(proposal_raw),
            'hypothesis_sha256': _sha(proposal['hypothesis'].encode()),
            'epoch_seconds': int(self.now()),
        })
        return {'round_index': round_index,
                'proposal_sha256': _sha(proposal_raw),
                'train_task_count': len(proposal['train_task_ids']),
                'paid_attempt_id': attempt_id,
                'billing_state': paid['billing_state']}

    def _rendered_train_batch(self, *, round_index: int,
                              rendered_batch: object,
                              dataset_manifest_path: Path,
                              training: dict) -> tuple[dict, list[int], list[int], str]:
        proposal_path = self.directory / f'proposal-{round_index:03d}.private.json'
        proposal, proposal_raw = _json(proposal_path, 'researcher_proposal')
        matching = [row for row in self._events('researcher_proposal')
                    if row['data']['round_index'] == round_index]
        _require(len(matching) == 1 and
                 matching[0]['data']['proposal_sha256'] == _sha(proposal_raw),
                 'researcher_proposal_not_frozen')
        dataset_path = _private_input(dataset_manifest_path,
                                      self.study.repo_root, 'train_dataset')
        dataset, dataset_raw = _json(dataset_path, 'train_dataset')
        _require(type(dataset) is dict and set(dataset) == {
            'schema', 'cell_id', 'action_profile', 'model',
            'train_task_ids', 'train_package_sha256_by_id',
            'episode_receipt_sha256s', 'rendered_batch_sha256',
            'admitted_train_only', 'selection_task_count',
            'final_task_count'},
            'train_dataset_shape_invalid')
        allowed = {row['task_id']: row['package_sha256']
                   for row in self.views['train']}
        task_ids = dataset['train_task_ids']
        _require(dataset['schema'] == 'cua-full-study-rendered-train-batch-v1' and
                 dataset['cell_id'] == self.intent['cell_id'] and
                 dataset['action_profile'] == 'scale-action-profile-v0.6.6' and
                 dataset['model'] == TINKER_MODEL and
                 dataset['admitted_train_only'] is True and
                 dataset['selection_task_count'] == 0 and
                 dataset['final_task_count'] == 0 and
                 type(task_ids) is list and task_ids and
                 len(task_ids) == len(set(task_ids)) and
                 set(task_ids) <= set(proposal['train_task_ids']) and
                 dataset['train_package_sha256_by_id'] == {
                     task_id: allowed[task_id] for task_id in task_ids
                 } and
                 type(dataset['episode_receipt_sha256s']) is list and
                 dataset['episode_receipt_sha256s'] and
                 all(cell_final.is_hash(value) for value in
                     dataset['episode_receipt_sha256s']) and
                 cell_final.is_hash(dataset['rendered_batch_sha256']),
                 'train_dataset_contains_unbound_or_evaluation_source')
        receipt = getattr(rendered_batch, 'receipt', None)
        datums = getattr(rendered_batch, 'datums', None)
        prompts = getattr(rendered_batch, 'prompts', None)
        _require(type(receipt) is dict and
                 receipt.get('schema') == 'cua-full-study-qwen-render-v066-v1' and
                 receipt.get('cell_id') == self.intent['cell_id'] and
                 receipt.get('action_profile') == 'scale-action-profile-v0.6.6' and
                 receipt.get('model') == TINKER_MODEL and
                 receipt.get('train_task_ids') == task_ids and
                 receipt.get('episode_receipt_sha256s') ==
                 dataset['episode_receipt_sha256s'] and
                 _sha(_canonical(receipt)) == dataset['rendered_batch_sha256'] and
                 type(datums) is list and type(prompts) is list and
                 datums and prompts and len(datums) == len(prompts) and
                 len(datums) <= training['batch_size'] *
                 training['optimizer_steps'],
                 'rendered_qwen_batch_not_bound_to_train_dataset')
        datum_lengths = receipt.get('datum_token_lengths')
        prompt_lengths = receipt.get('prompt_token_lengths')
        _require(type(datum_lengths) is list and
                 type(prompt_lengths) is list and
                 len(datum_lengths) == len(datums) and
                 len(prompt_lengths) == len(prompts),
                 'rendered_qwen_token_lengths_missing')
        for datum, prompt, datum_length, prompt_length in zip(
                datums, prompts, datum_lengths, prompt_lengths):
            _require(type(datum_length) is int and
                     type(prompt_length) is int and
                     0 < prompt_length < datum_length <=
                     training['max_supervised_tokens'] and
                     getattr(getattr(datum, 'model_input', None),
                             'length', None) == datum_length and
                     getattr(prompt, 'length', None) == prompt_length,
                     'rendered_qwen_datum_length_mismatch')
        return dataset, datum_lengths, prompt_lengths, _sha(dataset_raw)

    def dispatch_tinker_sft(self, *, round_index: int,
                            dataset_manifest_path: Path,
                            rendered_batch: object,
                            provider: Callable[[object, dict, list[list[int]]], dict] | None = None) -> dict:
        """Fresh-base Qwen LoRA SFT; only validated v0.6.6 train episodes.

        The caller supplies datums from an evaluator-bound renderer. The
        default provider calls the pinned Tinker SDK; tests inject a fake.
        Checkpoint paths stay in the mode-0600 private result file.
        """
        self._check_time()
        _require(type(round_index) is int and round_index > 0 and
                 not self._events('selection_frozen'),
                 'tinker_round_or_selection_freeze_invalid')
        training, training_sha = self.study.student_training_configuration()
        dataset, lengths, prompt_lengths, dataset_sha = self._rendered_train_batch(
            round_index=round_index, rendered_batch=rendered_batch,
            dataset_manifest_path=dataset_manifest_path, training=training)
        indices = [[(step * training['batch_size'] + offset) % len(lengths)
                    for offset in range(training['batch_size'])]
                   for step in range(training['optimizer_steps'])]
        _require(set(index for batch in indices for index in batch) ==
                 set(range(len(lengths))), 'training_schedule_omits_submitted_datum')
        scheduled_tokens = sum(lengths[index] for batch in indices
                               for index in batch)
        _require(scheduled_tokens <= training['max_scheduled_tokens'],
                 'frozen_training_token_cap_exceeded')
        quote = ((Decimal(scheduled_tokens) *
                  Decimal(training['train_usd_per_million_tokens']) +
                  Decimal(prompt_lengths[0]) *
                  Decimal(training['prefill_usd_per_million_tokens']) +
                  Decimal(training['sample_max_tokens']) *
                  Decimal(training['sample_usd_per_million_tokens'])) /
                 Decimal(1_000_000) *
                 Decimal(training['billing_multiplier_upper']))
        reserve = str(quote.quantize(Decimal('0.000000001'),
                                     rounding=ROUND_CEILING))
        _require(Decimal(reserve) > 0 and Decimal(reserve) <=
                 Decimal(self.intent['tinker_usd_cap']),
                 'tinker_worst_case_reservation_exceeds_campaign_cap')
        if provider is None:
            _require(bool(os.environ.get('TINKER_API_KEY')),
                     'tinker_key_missing_before_paid_reservation')
            provider = self._real_tinker_train
        attempt_id = f'tinker-{round_index:03d}'
        request = {
            'schema': 'cua-full-study-tinker-sft-request-v1',
            'model': TINKER_MODEL,
            'cell_id': self.intent['cell_id'],
            'researcher_id': self.intent['researcher_id'],
            'round_index': round_index,
            'dataset_manifest_sha256': dataset_sha,
            'rendered_batch_sha256': dataset['rendered_batch_sha256'],
            'training_config_sha256': training_sha,
            'optimizer_steps': training['optimizer_steps'],
            'batch_size': training['batch_size'],
            'scheduled_tokens': scheduled_tokens,
            'max_sample_tokens': training['sample_max_tokens'],
        }
        def call(_request):
            result = provider(rendered_batch, training, indices)
            _require(type(result) is dict and set(result) == {
                'checkpoint_path', 'observed_base_model',
                'optimizer_steps_completed', 'sample_token_count',
                'sample_token_sha256', 'sdk_operation_count'} and
                type(result['checkpoint_path']) is str and
                TINKER_PATH.fullmatch(result['checkpoint_path']) is not None and
                result['observed_base_model'] == TINKER_MODEL and
                result['optimizer_steps_completed'] ==
                training['optimizer_steps'] and
                type(result['sample_token_count']) is int and
                0 < result['sample_token_count'] <=
                training['sample_max_tokens'] and
                cell_final.is_hash(result['sample_token_sha256']) and
                type(result['sdk_operation_count']) is int and
                result['sdk_operation_count'] >=
                training['optimizer_steps'] * 2 + 2,
                'tinker_result_checkpoint_or_sample_invalid')
            return result
        paid = self.dispatch_paid(
            attempt_id=attempt_id, category='tinker',
            work=request, request=request,
            reserve_usd=reserve,
            resource_reservation={'candidate_submissions': '1'}, provider=call)
        checkpoint_sha = _sha(paid['result']['checkpoint_path'].encode())
        self.journal.append('tinker_checkpoint', {
            'round_index': round_index, 'paid_attempt_id': attempt_id,
            'dataset_manifest_sha256': dataset_sha,
            'training_config_sha256': training_sha,
            'checkpoint_path_sha256': checkpoint_sha,
            'optimizer_steps': training['optimizer_steps'],
            'scheduled_tokens': scheduled_tokens,
            'epoch_seconds': int(self.now()),
        })
        return {'round_index': round_index,
                'checkpoint_path_sha256': checkpoint_sha,
                'optimizer_steps': training['optimizer_steps'],
                'scheduled_tokens': scheduled_tokens,
                'billing_state': paid['billing_state']}

    def _real_tinker_train(self, rendered_batch: object,
                           training: dict, indices: list[list[int]]) -> dict:
        import tinker
        from tinker import types
        service = tinker.ServiceClient(user_metadata={
            'purpose': 'envloop-full-study-train-only-v1',
            'study_id': self.study.plan['study_id'],
            'cell_id': self.intent['cell_id'],
            'researcher_id': self.intent['researcher_id'],
            'split': 'train',
        })
        status = 'errored'
        calls = 0
        try:
            client = service.create_lora_training_client(
                base_model=TINKER_MODEL, rank=training['lora_rank'],
                seed=training['seed'])
            calls += 1
            for batch_indices in indices:
                batch = [rendered_batch.datums[index] for index in batch_indices]
                client.forward_backward(batch, 'cross_entropy').result(timeout=300)
                calls += 1
                client.optim_step(types.AdamParams(
                    learning_rate=float(training['learning_rate']))).result(timeout=300)
                calls += 1
            name = ('envloop-' + self.intent['cell_id'] + '-' +
                    self.intent['researcher_id'] + '-train')
            checkpoint = client.save_weights_for_sampler(name).result(timeout=300)
            calls += 1
            sampler = service.create_sampling_client(model_path=checkpoint.path)
            calls += 1
            observed_base = sampler.get_base_model()
            sample = sampler.sample(
                prompt=rendered_batch.prompts[0], num_samples=1,
                sampling_params=types.SamplingParams(
                    max_tokens=training['sample_max_tokens'],
                    temperature=0, seed=training['seed'])).result(timeout=300)
            calls += 1
            tokens = sample.sequences[0].tokens
            status = 'success'
            return {
                'checkpoint_path': checkpoint.path,
                'observed_base_model': observed_base,
                'optimizer_steps_completed': len(indices),
                'sample_token_count': len(tokens),
                'sample_token_sha256': _sha(str(tokens).encode()),
                'sdk_operation_count': calls,
            }
        finally:
            service.close(status).result(timeout=30)

    def _selection_attempts(self, round_index: int) -> list[dict]:
        return [row for row in self._events('selection_started')
                if row['data']['round_index'] == round_index]

    def _selection_completion(self, attempt_id: str) -> dict | None:
        matches = [row for row in self._events()
                   if row['kind'] in {'selection_scored', 'selection_invalid'} and
                   row['data']['attempt_id'] == attempt_id]
        _require(len(matches) <= 1, 'selection_attempt_completed_twice')
        return matches[0] if matches else None

    def _selection_paid_coverage(self, *, attempt_id: str,
                                 checkpoint_sha256: str,
                                 paid_attempt_ids: list[str]) -> dict:
        """Reopen exact paid requests; category presence alone is not coverage."""
        self._audit_paid_files()
        starts = [row for row in self._events('selection_started')
                  if row['data']['attempt_id'] == attempt_id]
        _require(len(starts) == 1, 'selection_paid_start_missing')
        start = starts[0]
        related = [row for row in self._events('paid_intent')
                   if row['data']['attempt_id'].startswith(attempt_id + '-')]
        _require(all(row['sequence'] > start['sequence'] for row in related),
                 'selection_paid_before_attempt_start')
        by_id = {row['data']['attempt_id']: row['data'] for row in related}
        completed = {row['data']['attempt_id'] for row in
                     self._events('paid_result')}
        _require(type(paid_attempt_ids) is list and
                 len(paid_attempt_ids) == len(set(paid_attempt_ids)) and
                 set(paid_attempt_ids) == set(by_id),
                 'selection_paid_attempt_hidden_or_missing')
        calls = []
        for paid_id in paid_attempt_ids:
            request, raw = _json(self.directory /
                                 f'{paid_id}.request.private.json',
                                 'selection_paid_request')
            _require(_sha(raw) == by_id[paid_id]['request_sha256'],
                     'selection_paid_request_changed')
            calls.append({
                'attempt_id': paid_id,
                'category': by_id[paid_id]['category'],
                'request': request,
                'result_present': paid_id in completed,
            })
        try:
            return paid_coverage.validate(
                cell_id=self.intent['cell_id'], attempt_id=attempt_id,
                checkpoint_sha256=checkpoint_sha256,
                selection_tasks=list(self.views['selection']),
                selection_identities_sha256=
                    start['data']['selection_identities_sha256'],
                paid_calls=calls,
                related_paid_attempt_ids=set(by_id))
        except ValueError as exc:
            raise DispatchError(str(exc)) from None

    def _verify_selection_coverage_event(self, event: dict) -> None:
        data = event['data']
        attempt_id = data['attempt_id']
        expected = self._selection_paid_coverage(
            attempt_id=attempt_id,
            checkpoint_sha256=data['checkpoint_path_sha256'],
            paid_attempt_ids=data['paid_attempt_ids'])
        saved, raw = _json(self.directory /
                           f'selection-{attempt_id}-paid-coverage.private.json',
                           'selection_paid_coverage')
        _require(saved == expected and
                 data.get('paid_coverage_sha256') == _sha(raw),
                 'selection_paid_coverage_receipt_changed')

    def start_selection_attempt(self, *, round_index: int, attempt_id: str,
                                retry_rule_sha256: str | None = None) -> dict:
        """Reserve one complete 20-task original-software selection execution.

        A cell-owned GUI worker takes the returned selection-only identities,
        calls providers through ``dispatch_paid`` and later registers one
        saved-state result. No final package can enter this view.
        """
        self._check_time()
        _require(type(round_index) is int and round_index > 0 and
                 type(attempt_id) is str and
                 dollars.ATTEMPT.fullmatch(attempt_id) is not None and
                 not self._events('selection_frozen'),
                 'selection_start_contract_invalid')
        checkpoint_rows = [row for row in self._events('tinker_checkpoint')
                           if row['data']['round_index'] == round_index]
        _require(len(checkpoint_rows) == 1,
                 'selection_requires_one_trained_checkpoint')
        prior = self._selection_attempts(round_index)
        _require(len(prior) < 2 and
                 not any(row['data']['attempt_id'] == attempt_id
                         for row in self._events('selection_started')),
                 'selection_attempt_limit_or_duplicate')
        if prior:
            previous = self._selection_completion(prior[0]['data']['attempt_id'])
            _require(previous is not None and
                     previous['kind'] == 'selection_invalid' and
                     cell_final.is_hash(retry_rule_sha256) and
                     not self._unresolved_failure() and
                     not self._inflight_attempts(),
                     'selection_retry_requires_preserved_invalid_and_rule')
        else:
            _require(retry_rule_sha256 is None,
                     'first_selection_attempt_cannot_claim_retry_rule')
        _require(self._counter_totals()['selection_evaluations'] + 1 <=
                 Decimal(self.intent['matched_count_caps']
                         ['selection_evaluations_per_campaign']),
                 'selection_evaluation_cap_exhausted')
        selection_view = list(self.views['selection'])
        view_sha = _sha(_canonical(selection_view))
        checkpoint_sha = checkpoint_rows[0]['data']['checkpoint_path_sha256']
        self.journal.append('selection_started', {
            'round_index': round_index, 'attempt_id': attempt_id,
            'checkpoint_path_sha256': checkpoint_sha,
            'selection_identities_sha256': view_sha,
            'task_count': matrix.SELECTION_PER_CELL,
            'retry_rule_sha256': retry_rule_sha256,
            'epoch_seconds': int(self.now()),
        })
        return {'attempt_id': attempt_id,
                'checkpoint_path_sha256': checkpoint_sha,
                'selection_tasks': selection_view,
                'selection_identities_sha256': view_sha,
                'task_count': matrix.SELECTION_PER_CELL}

    def record_selection_invalid(self, *, attempt_id: str,
                                 failure_type: str,
                                 evaluator_receipt_sha256: str) -> dict:
        """Keep an invalid GUI/provider attempt visible, never score it zero."""
        starts = [row for row in self._events('selection_started')
                  if row['data']['attempt_id'] == attempt_id]
        _require(len(starts) == 1 and
                 self._selection_completion(attempt_id) is None and
                 failure_type in {'provider', 'transport', 'environment',
                                  'verifier'} and
                 cell_final.is_hash(evaluator_receipt_sha256),
                 'selection_invalid_receipt_or_attempt_missing')
        row = self.journal.append('selection_invalid', {
            'attempt_id': attempt_id,
            'round_index': starts[0]['data']['round_index'],
            'failure_type': failure_type,
            'evaluator_receipt_sha256': evaluator_receipt_sha256,
            'epoch_seconds': int(self.now()),
        })
        return row['data']

    def _incumbent(self) -> tuple[str, dict[str, int]]:
        base, base_raw = _json(self.directory / 'base-selection.private.json',
                               'base_selection')
        base_events = self._events('base_selection')
        _require(len(base_events) == 1 and
                 base_events[0]['data']['result_sha256'] == _sha(base_raw),
                 'base_selection_receipt_changed')
        scores = self._selection_result(
            base, checkpoint_sha256=self.intent['base_checkpoint_sha256'])
        checkpoint = self.intent['base_checkpoint_sha256']
        for event in self._events('selection_scored'):
            self._verify_selection_coverage_event(event)
            result, raw = _json(
                self.directory /
                f"selection-{event['data']['attempt_id']}.private.json",
                'selection_scored')
            _require(_sha(raw) == event['data']['result_sha256'],
                     'selection_result_changed_after_scoring')
            candidate = self._selection_result(
                result,
                checkpoint_sha256=event['data']['checkpoint_path_sha256'])
            regressions = sum(candidate[key] < scores[key] for key in scores)
            promoted = sum(candidate.values()) > sum(scores.values()) and\
                regressions == 0
            _require(promoted == event['data']['promoted'] and
                     regressions == event['data']['regressions_vs_incumbent'] and
                     sum(candidate.values()) == event['data']['score_wins'] and
                     checkpoint == event['data']
                     ['incumbent_before_checkpoint_sha256'] and
                     (result['checkpoint_sha256'] if promoted else checkpoint) ==
                     event['data']['incumbent_after_checkpoint_sha256'],
                     'selection_promotion_rule_or_scores_changed')
            if promoted:
                checkpoint, scores = result['checkpoint_sha256'], candidate
        return checkpoint, scores

    def record_selection_scored(self, *, attempt_id: str, result: dict,
                                paid_attempt_ids: list[str]) -> dict:
        self._check_time()
        starts = [row for row in self._events('selection_started')
                  if row['data']['attempt_id'] == attempt_id]
        _require(len(starts) == 1 and
                 self._selection_completion(attempt_id) is None and
                 type(paid_attempt_ids) is list and
                 len(paid_attempt_ids) == len(set(paid_attempt_ids)) and
                 paid_attempt_ids,
                 'selection_scored_attempt_or_cost_calls_invalid')
        started = starts[0]['data']
        scores = self._selection_result(
            result, checkpoint_sha256=started['checkpoint_path_sha256'])
        # All provider work used by the cell worker must be retained in this
        # campaign's paid ledger. Qwen sampling and the actual original-
        # software environment class are required; self-hosted applications
        # must not fabricate E2B leases. Billing settles before freeze.
        paid = {row['data']['attempt_id']: row['data']
                for row in self._events('paid_intent')}
        selection_started_sequence = starts[0]['sequence']
        selection_paid = [row for row in self._events('paid_intent')
                          if row['data']['attempt_id'] in paid_attempt_ids]
        _require(set(paid_attempt_ids) <= set(paid) and
                 all(paid_id.startswith(attempt_id + '-')
                     for paid_id in paid_attempt_ids) and
                 all(row['sequence'] > selection_started_sequence for row in
                     selection_paid) and
                 set(paid_attempt_ids) <= {
                     row['data']['attempt_id'] for row in
                     self._events('paid_result')} and
                 selection_environment.paid_categories_valid(
                     self.intent['cell_id'],
                     {paid[paid_id]['category']
                      for paid_id in paid_attempt_ids}),
                 'selection_sampler_or_environment_cost_missing')
        coverage = self._selection_paid_coverage(
            attempt_id=attempt_id,
            checkpoint_sha256=started['checkpoint_path_sha256'],
            paid_attempt_ids=paid_attempt_ids)
        current_checkpoint, incumbent = self._incumbent()
        regressions = sum(scores[key] < incumbent[key] for key in scores)
        promoted = sum(scores.values()) > sum(incumbent.values()) and\
            regressions == 0
        raw = _canonical(result)
        _private_write_new(self.directory /
                           f'selection-{attempt_id}.private.json', raw)
        coverage_raw = _canonical(coverage)
        _private_write_new(self.directory /
                           f'selection-{attempt_id}-paid-coverage.private.json',
                           coverage_raw)
        self.journal.append('selection_scored', {
            'attempt_id': attempt_id,
            'round_index': started['round_index'],
            'checkpoint_path_sha256': started['checkpoint_path_sha256'],
            'result_sha256': _sha(raw),
            'score_wins': sum(scores.values()),
            'regressions_vs_incumbent': regressions,
            'promoted': promoted,
            'incumbent_before_checkpoint_sha256': current_checkpoint,
            'incumbent_after_checkpoint_sha256': (
                started['checkpoint_path_sha256'] if promoted else
                current_checkpoint),
            'paid_attempt_ids': paid_attempt_ids,
            'paid_coverage_sha256': _sha(coverage_raw),
            'epoch_seconds': int(self.now()),
        })
        return {'attempt_id': attempt_id,
                'score_wins': sum(scores.values()),
                'regressions_vs_incumbent': regressions,
                'promoted': promoted,
                'selected_checkpoint_path_sha256': (
                    started['checkpoint_path_sha256'] if promoted else
                    current_checkpoint)}

    def freeze_selection(self) -> dict:
        """Freeze selected checkpoint before any hidden final evaluation."""
        self._check_time()
        self._audit_paid_files()
        _require(not self._events('selection_frozen') and
                 self._events('tinker_checkpoint') and
                 self._events('selection_scored') and
                 not self._inflight_attempts() and
                 not self._orphan_budget_attempts() and
                 not self._unresolved_failure(),
                 'selection_freeze_requires_complete_reconciled_search')
        for start in self._events('selection_started'):
            _require(self._selection_completion(start['data']['attempt_id'])
                     is not None,
                     'selection_attempt_unresolved')
        state = self.budget.owner_attempts(self.owner)
        _require(all(row['status'] in {'settled', 'cancelled'} for row in
                     state.values()),
                 'provider_usage_not_reconciled_before_selection_freeze')
        checkpoint, scores = self._incumbent()
        started = self._events('campaign_started')[0]['data']['epoch_seconds']
        frozen_at = int(self.now())
        checkpoints = [row['data'] for row in self._events('tinker_checkpoint')]
        selections = [row['data'] for row in self._events('selection_scored')]
        receipt = {
            'schema': 'cua-full-study-selection-freeze-v1',
            'cell_id': self.intent['cell_id'],
            'researcher_id': self.intent['researcher_id'],
            'base_checkpoint_sha256': self.intent['base_checkpoint_sha256'],
            'selected_checkpoint_sha256': checkpoint,
            'training_lineage_sha256': _sha(_canonical(checkpoints)),
            'selection_results_sha256': _sha(_canonical(selections)),
            'selection_frozen_at': frozen_at,
            'campaign_started_at': started,
            'campaign_finished_at': frozen_at,
            'candidate_count': int(
                self._counter_totals()['candidate_submissions']),
            'selection_evaluations': int(
                self._counter_totals()['selection_evaluations']),
        }
        raw = _canonical(receipt)
        _private_write_new(self.directory / 'selection-freeze.private.json', raw)
        self.journal.append('selection_frozen', {
            'freeze_sha256': _sha(raw),
            'selected_checkpoint_sha256': checkpoint,
            'selected_selection_wins': sum(scores.values()),
            'epoch_seconds': frozen_at,
        })
        return {'selection_freeze_sha256': _sha(raw),
                'selected_checkpoint_sha256': checkpoint,
                'selected_selection_wins': sum(scores.values()),
                'candidate_count': receipt['candidate_count'],
                'selection_evaluations': receipt['selection_evaluations']}

    def dispatch_paid(self, *, attempt_id: str, category: str,
                      work: object, request: object, reserve_usd: str,
                      resource_reservation: dict[str, str],
                      provider: Callable[[object], object]) -> dict:
        """Commit the exact request before invoking one provider callback.

        The callback is invoked at most once by this method. On interruption,
        the existing intent/dispatched dollar reservation blocks replay. The
        caller must reconcile actual provider usage independently.
        """
        with self._operation_lock():
            return self._dispatch_paid_locked(
                attempt_id=attempt_id, category=category, work=work,
                request=request, reserve_usd=reserve_usd,
                resource_reservation=resource_reservation,
                provider=provider)

    def _dispatch_paid_locked(self, *, attempt_id: str, category: str,
                              work: object, request: object,
                              reserve_usd: str,
                              resource_reservation: dict[str, str],
                              provider: Callable[[object], object]) -> dict:
        self._check_time()
        self._audit_paid_files()
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
        units = self._check_resources(category, resource_reservation, request)
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
            provider_receipt = (result.get('receipt') if
                                type(result) is dict else None)
            usage = (provider_receipt.get('usage') if
                     type(provider_receipt) is dict else
                     result.get('usage') if type(result) is dict else None)
            usage_counts = None
            if (type(usage) is dict and
                    type(usage.get('input_tokens')) is int and
                    type(usage.get('output_tokens')) is int and
                    usage['input_tokens'] >= 0 and
                    usage['output_tokens'] >= 0):
                usage_counts = {'input_tokens': usage['input_tokens'],
                                'output_tokens': usage['output_tokens']}
            self.journal.append('paid_result', {
                'attempt_id': attempt_id,
                'result_sha256': _sha(result_raw),
                'provider_token_usage': usage_counts,
                'epoch_seconds': int(self.now()),
            })
            return {'attempt_id': attempt_id, 'result': result,
                    'result_sha256': _sha(result_raw),
                    'billing_state': 'awaiting_provider_usage_reconciliation'}
        except Exception as exc:
            failure_type = ('verifier' if isinstance(exc, DispatchError) else
                            'provider' if type(exc).__name__ in
                            {'ProviderFailure', 'APIStatusError'} else
                            'transport')
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
        self._audit_paid_files()
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
        self._audit_paid_files()
        events = self._events()
        counters = self._counter_totals()
        tokens = {'provider_input_tokens': 0,
                  'provider_output_tokens': 0,
                  'tinker_scheduled_train_tokens': 0,
                  'provider_results_without_token_usage': 0}
        for event in self._events('paid_result'):
            usage = event['data'].get('provider_token_usage')
            if usage is None:
                tokens['provider_results_without_token_usage'] += 1
            else:
                tokens['provider_input_tokens'] += usage['input_tokens']
                tokens['provider_output_tokens'] += usage['output_tokens']
        tokens['tinker_scheduled_train_tokens'] = sum(
            event['data']['scheduled_tokens'] for event in
            self._events('tinker_checkpoint'))
        cost = {name: {'reserved_or_reconciled_usd': Decimal(0),
                       'reconciled_usd': Decimal(0),
                       'unreconciled_reserve_usd': Decimal(0)}
                for name in dollars.CAMPAIGN_CATEGORIES if
                name != 'selected_final'}
        for record in self.budget.owner_attempts(self.owner).values():
            item = cost[record['category']]
            if record['status'] == 'cancelled':
                continue
            if record['status'] in {'settled', 'overrun'}:
                amount = Decimal(record['actual_usd'])
                item['reconciled_usd'] += amount
            else:
                amount = Decimal(record['reserved_usd'])
                item['unreconciled_reserve_usd'] += amount
            item['reserved_or_reconciled_usd'] += amount
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
                'token_telemetry': tokens,
                'cost_accounting_usd': {
                    name: {key: str(value) for key, value in row.items()}
                    for name, row in cost.items()},
                'selection_frozen': bool(self._events('selection_frozen')),
                'journal_head_sha256': events[-1]['hash'] if events else
                    self.journal.rows()[0]['hash']}
