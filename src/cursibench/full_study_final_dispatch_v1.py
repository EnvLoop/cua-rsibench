"""Fail-closed final-task dispatcher for the frozen six-cell study.

This module supplies the missing execution boundary between the post-campaign
matrix and the results auditor. It does not contain a cell worker, a credential,
or a final task. A trusted original-software worker receives one opaque task
identity and frozen execution policy at a time; evaluator-owned package loading,
GUI observation/action dispatch, saved-state scoring, and cold reset stay inside
that worker. The controller verifies its private evidence, accounts for cost,
and preserves every attempt. A hash is integrity evidence, not proof that a GUI
trace is true; independent cell review remains mandatory for publication.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Callable, Protocol

from . import full_study_budget_v1 as budget_mod
from . import full_study_campaign_dispatch_v1 as campaign
from . import full_study_matrix_v1 as matrix
from . import full_study_results_v1 as results
from . import scale_final_v06 as evidence


GATE_SCHEMA = 'cua-full-study-final-dispatch-gate-v1'
PUBLIC_FINAL_SCHEMA = 'cua-full-study-public-final-dispatch-freeze-v1'
PUBLIC_FINAL_PATH = 'docs/evidence/full-study-final-dispatch-freeze.json'
JOURNAL_SCHEMA = 'cua-full-study-final-dispatch-journal-v1'
WORKER_SCHEMA = 'cua-full-study-trusted-final-worker-v1'
COMMAND_SCHEMA = 'cua-full-study-final-task-command-v1'
OUTCOME_SCHEMA = 'cua-full-study-final-worker-outcome-v1'
VERIFIER_SCHEMA = 'cua-full-study-final-independent-verifier-v1'
RESET_SCHEMA = 'cua-full-study-final-cold-reset-v1'
TRACE_SCHEMA = 'cua-full-study-final-gui-trace-v1'
USAGE_SCHEMA = 'cua-full-study-final-provider-usage-v1'
ATTEMPT_SCHEMA = 'cua-full-study-final-attempt-receipt-v1'
RETRY_RULE = {
    'schema': 'cua-full-study-final-infrastructure-retry-rule-v1',
    'maximum_retries_per_task': 1,
    'eligible_failure_types': sorted(results.FAILURE_TYPES),
    'require_reconciled_provider_usage': True,
    'require_cold_reset_before_retry': True,
    'never_replay_uncertain_dispatch': True,
}
RETRY_RULE_SHA256 = hashlib.sha256(evidence.json_bytes(RETRY_RULE)).hexdigest()
SAMPLER_PATH = re.compile(r'tinker://[^\s/]+/sampler_weights/[^\s/]+\Z')
MAX_PRIVATE_BYTES = 128 * 1024 * 1024


class FinalDispatchError(ValueError):
    """A local protocol failure; never contains private task instructions."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise FinalDispatchError(code)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def private_json(path: Path, work_root: Path, label: str) -> tuple[dict, bytes]:
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            path.resolve().is_relative_to(work_root.resolve()) and
            path.stat().st_mode & 0o077 == 0 and
            0 < path.stat().st_size <= MAX_PRIVATE_BYTES,
            f'{label}_private_file_required')
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise FinalDispatchError(f'{label}_invalid_json') from None
    require(type(value) is dict, f'{label}_object_required')
    return value, raw


def private_reference(root: Path, reference: object, label: str) -> tuple[Path, bytes]:
    require(type(reference) is dict and set(reference) == {'path', 'sha256'},
            f'{label}_reference_invalid')
    relative = reference['path']
    require(type(relative) is str and relative and '\\' not in relative and
            evidence.is_hash(reference['sha256']), f'{label}_reference_invalid')
    path = Path(relative)
    require(not path.is_absolute() and all(part not in ('', '.', '..')
                                           for part in path.parts),
            f'{label}_reference_unsafe')
    target = root / path
    require(target.is_file() and not target.is_symlink() and
            target.resolve().is_relative_to(root.resolve()) and
            target.stat().st_mode & 0o077 == 0 and
            target.stat().st_size <= MAX_PRIVATE_BYTES,
            f'{label}_private_file_required')
    raw = target.read_bytes()
    require(sha(raw) == reference['sha256'], f'{label}_bytes_changed')
    return target, raw


def private_write_new(path: Path, raw: bytes) -> None:
    require(not path.exists() and not path.is_symlink(), 'private_output_exists')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def reference(root: Path, path: Path) -> dict:
    path = path.resolve()
    require(path.is_relative_to(root.resolve()), 'private_reference_outside_work')
    return {'path': path.relative_to(root.resolve()).as_posix(),
            'sha256': sha(path.read_bytes())}


def _campaign_journal(study: campaign.FrozenStudy, path: Path,
                      cell_id: str, researcher_id: str,
                      freeze_sha256: str, freeze: dict) -> None:
    intent = study.intents[(cell_id, researcher_id)]
    header = {
        'schema': campaign.JOURNAL_SCHEMA, 'kind': 'header',
        'plan_sha256': study.plan_sha256,
        'intent_sha256': intent['intent_sha256'],
        'ratification_sha256': study.ratification_sha256,
        'public_witness_sha256': study.public_witness_sha256,
        'owner': f'{cell_id}:{researcher_id}',
    }
    # The constructor is read-only because private_reference already proved
    # that the journal exists; rows() verifies its full SHA chain.
    rows = campaign.CampaignJournal(path, header).rows()
    starts = [row for row in rows[1:] if row['kind'] == 'campaign_started']
    checkpoints = [row['data'] for row in rows[1:]
                   if row['kind'] == 'tinker_checkpoint']
    selections = [row['data'] for row in rows[1:]
                  if row['kind'] == 'selection_scored']
    freezes = [row for row in rows[1:] if row['kind'] == 'selection_frozen']
    require(len(starts) == 1 and checkpoints and selections and
            starts[0]['data']['epoch_seconds'] == freeze['campaign_started_at'] and
            sha(campaign._canonical(checkpoints)) ==
                freeze['training_lineage_sha256'] and
            sha(campaign._canonical(selections)) ==
                freeze['selection_results_sha256'] and
            len(freezes) == 1 and rows[-1] == freezes[0] and
            freezes[0]['data']['freeze_sha256'] == freeze_sha256 and
            freezes[0]['data']['selected_checkpoint_sha256'] ==
                freeze['selected_checkpoint_sha256'] and
            freezes[0]['data']['epoch_seconds'] == freeze['selection_frozen_at'],
            'campaign_journal_selection_freeze_unbound')


class FinalGate:
    """Rebuild 600 admissions and all 24 frozen campaigns before any task."""

    def __init__(self, *, frozen: campaign.FrozenStudy,
                 matrix_manifest_path: Path, prepared_matrix_dir: Path,
                 completion_index_path: Path,
                 final_public_commit_sha1: str,
                 witness_fetcher: Callable[[str], bytes] | None = None):
        require(type(frozen) is campaign.FrozenStudy,
                'real_pre_campaign_freeze_required')
        self.frozen = frozen
        self.work_root = frozen.repo_root / 'work'
        self.matrix_manifest_path = Path(matrix_manifest_path).resolve()
        self.prepared_matrix_dir = Path(prepared_matrix_dir).resolve()
        manifest, raw = private_json(self.matrix_manifest_path, self.work_root,
                                     'matrix_manifest')
        self.manifest = manifest
        pre_ref = manifest.get('pre_campaign_protocol')
        pre_plan_ref = manifest.get('pre_campaign_plan')
        pre_path, pre_raw = evidence.evidence_file(
            self.matrix_manifest_path.parent, pre_ref, 'pre-campaign protocol')
        _, pre_plan_raw = evidence.evidence_file(
            self.matrix_manifest_path.parent, pre_plan_ref, 'pre-campaign plan')
        require(pre_path.resolve() == frozen.manifest_path and
                pre_raw == frozen.manifest_path.read_bytes() and
                pre_plan_raw == frozen.plan_raw,
                'matrix_not_bound_to_public_pre_campaign_freeze')
        self.plan = matrix.build(manifest, self.matrix_manifest_path.parent,
                                 sha(raw))
        self.initial_state_by_task = {}
        for cell_entry in manifest['cells']:
            cell_id = cell_entry['cell_id']
            base, _, base_path = matrix._json_reference(
                self.matrix_manifest_path.parent, cell_entry['base_manifest'],
                f'{cell_id} base manifest')
            qualification, _, _ = matrix._json_reference(
                base_path.parent, base['qualification_evidence'],
                f'{cell_id} qualification')
            expected = {}
            for row in qualification['official_tasks']:
                reset, _, _ = matrix._json_reference(
                    base_path.parent, row['reset']['evidence'],
                    f'{cell_id} qualified reset')
                expected[row['task_id']] = reset['initial_state_sha256']
            require(len(expected) == 100,
                    'qualified_initial_state_coverage_incomplete')
            self.initial_state_by_task[cell_id] = expected
        self.plan_raw = evidence.json_bytes(self.plan)
        self.plan_sha256 = sha(self.plan_raw)
        plan_path = self.prepared_matrix_dir / 'matrix-plan.json'
        intent_path = self.prepared_matrix_dir / 'intent.json'
        require(plan_path.is_file() and not plan_path.is_symlink() and
                plan_path.read_bytes() == self.plan_raw,
                'prepared_matrix_plan_missing_or_changed')
        expected_intent = {
            'schema': matrix.INTENT_SCHEMA, 'study_id': self.plan['study_id'],
            'matrix_manifest_sha256': self.plan['matrix_manifest_sha256'],
            'plan_sha256': self.plan_sha256,
            'cell_ids': list(matrix.CELLS), 'campaign_count': 24,
            'provider_dispatch_enabled': False, 'scores_present': False,
        }
        intent, _ = private_json(intent_path, self.work_root, 'matrix_intent')
        require(intent == expected_intent, 'prepared_matrix_intent_changed')
        require(self.plan['campaign_count'] == 24 and
                self.plan['distinct_official_task_identities'] == 600 and
                self.plan['initial_total_slot_task_results'] == 3000,
                'full_matrix_shape_required')
        index_path = Path(completion_index_path).resolve()
        index, index_raw = private_json(index_path, self.work_root,
                                        'completion_index')
        self.completion_index_path = index_path
        self.completion_index_sha256 = sha(index_raw)
        require(set(index) == {'schema', 'study_id', 'matrix_plan_sha256',
                               'retry_rule_sha256', 'campaigns'} and
                index['schema'] == GATE_SCHEMA and
                index['study_id'] == self.plan['study_id'] and
                index['matrix_plan_sha256'] == self.plan_sha256 and
                index['retry_rule_sha256'] == RETRY_RULE_SHA256 and
                type(index['campaigns']) is list and
                len(index['campaigns']) == 24,
                'completion_index_not_frozen_full_matrix')
        by_cell = {row['cell_id']: row for row in self.plan['cells']}
        self.freezes = {}
        self.freeze_raw_sha256s = {}
        for entry in index['campaigns']:
            require(type(entry) is dict and set(entry) == {
                'cell_id', 'researcher_id', 'selection_freeze', 'campaign_journal'},
                'completion_campaign_entry_invalid')
            cell_id, researcher_id = entry['cell_id'], entry['researcher_id']
            key = (cell_id, researcher_id)
            require(cell_id in by_cell and researcher_id in matrix.RESEARCHERS and
                    key not in self.freezes, 'completion_campaign_duplicate_or_unknown')
            freeze_path, freeze_raw = private_reference(
                self.work_root, entry['selection_freeze'], 'selection_freeze')
            journal_path, _ = private_reference(
                self.work_root, entry['campaign_journal'], 'campaign_journal')
            cell = by_cell[cell_id]
            base = cell['base']['bindings']['checkpoint']
            selected = cell['researcher_plans'][researcher_id]['bindings']['checkpoint']
            freeze = results._freeze(json.loads(freeze_raw), cell_id=cell_id,
                                      researcher_id=researcher_id,
                                      checkpoint=selected, base_checkpoint=base)
            _campaign_journal(frozen, journal_path, cell_id, researcher_id,
                              sha(freeze_raw), freeze)
            self.freezes[key] = freeze
            self.freeze_raw_sha256s[key] = sha(freeze_raw)
        require(set(self.freezes) == {(cell, rid) for cell in matrix.CELLS
                                      for rid in matrix.RESEARCHERS},
                'all_24_campaigns_must_freeze_before_final_dispatch')
        self.last_selection_frozen_at = max(
            row['selection_frozen_at'] for row in self.freezes.values())
        require(campaign.HEX40.fullmatch(final_public_commit_sha1) is not None,
                'immutable_public_final_commit_required')
        url = ('https://raw.githubusercontent.com/EnvLoop/cua-rsibench/' +
               final_public_commit_sha1 + '/' + PUBLIC_FINAL_PATH)
        witness_raw = campaign._fetch_immutable_witness(url, witness_fetcher)
        try:
            witness = json.loads(witness_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FinalDispatchError('public_final_witness_invalid_json') from None
        expected_witness = {
            'schema': PUBLIC_FINAL_SCHEMA,
            'status': 'frozen_before_first_final_dispatch',
            'study_id': self.plan['study_id'],
            'pre_campaign_public_witness_sha256': frozen.public_witness_sha256,
            'matrix_manifest_sha256': self.plan['matrix_manifest_sha256'],
            'matrix_plan_sha256': self.plan_sha256,
            'completion_index_sha256': self.completion_index_sha256,
            'ratification_sha256': frozen.ratification_sha256,
            'retry_rule_sha256': RETRY_RULE_SHA256,
            'selection_freeze_sha256_by_campaign': {
                f'{cell_id}:{researcher_id}': digest
                for (cell_id, researcher_id), digest in
                sorted(self.freeze_raw_sha256s.items())},
            'official_final_model_attempts_before_freeze': 0,
        }
        require(witness == expected_witness,
                'public_final_witness_does_not_bind_24_frozen_campaigns')
        self.public_final_witness_url = url
        self.public_final_witness_sha256 = sha(witness_raw)
        budget_path = self.work_root / 'full-study-budget.jsonl'
        require(budget_path.is_file() and not budget_path.is_symlink() and
                budget_path.stat().st_mode & 0o077 == 0,
                'campaign_budget_ledger_missing')
        self.budget = budget_mod.StudyBudgetLedger(budget_path, frozen.plan)
        snapshot = self.budget.snapshot()
        require(not snapshot['paid_dispatch_frozen'] and
                all(snapshot[key] == 0 for key in (
                    'pending_attempts', 'dispatched_attempts',
                    'uncertain_attempts', 'provider_overrun_attempts')),
                'campaign_provider_usage_unreconciled')
        for cell_id, researcher_id in self.freezes:
            attempts = self.budget.owner_attempts(f'{cell_id}:{researcher_id}')
            require(any(row['category'] == 'tinker' and
                        row['status'] == 'settled' for row in attempts.values()) and
                    all(row['status'] in ('settled', 'cancelled')
                        for row in attempts.values()),
                    'campaign_tinker_or_usage_unreconciled')


class TrustedFinalWorker(Protocol):
    """Evaluator-owned adapter; no model-facing gold or verifier capability."""

    @property
    def identity(self) -> dict: ...

    def run_once(self, command: dict, output_dir: Path) -> dict: ...


class FinalJournal:
    """Private append-only event log; an incomplete dispatch never replays."""

    def __init__(self, path: Path, header: dict):
        self.path, self.header = path, header
        self.lock_path = path.with_name('.' + path.name + '.lock')
        if not path.exists():
            private_write_new(path, canonical({**header, 'previous': None,
                                               'hash': sha(canonical({**header,
                                                                      'previous': None}))}))
        self.rows()

    def rows(self) -> list[dict]:
        require(self.path.is_file() and not self.path.is_symlink() and
                self.path.stat().st_mode & 0o077 == 0,
                'final_journal_private_file_required')
        try:
            rows = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise FinalDispatchError('final_journal_invalid_json') from None
        require(bool(rows), 'final_journal_empty')
        previous = None
        for index, row in enumerate(rows):
            core = {key: value for key, value in row.items() if key != 'hash'}
            require(row.get('previous') == previous and
                    row.get('hash') == sha(canonical(core)),
                    'final_journal_hash_chain_broken')
            if index == 0:
                require(core == {**self.header, 'previous': None},
                        'final_journal_header_changed')
            else:
                require(row.get('schema') == JOURNAL_SCHEMA and
                        row.get('sequence') == index and
                        row.get('kind') in {'attempt_intent', 'attempt_result',
                                            'attempt_uncertain', 'task_result'},
                        'final_journal_event_invalid')
            previous = row['hash']
        return rows

    def append(self, kind: str, data: dict) -> dict:
        require(kind in {'attempt_intent', 'attempt_result',
                         'attempt_uncertain', 'task_result'} and type(data) is dict,
                'final_journal_event_invalid')
        with self.lock_path.open('a') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            rows = self.rows()
            core = {'schema': JOURNAL_SCHEMA, 'kind': kind,
                    'sequence': len(rows), 'data': data,
                    'previous': rows[-1]['hash']}
            row = {**core, 'hash': sha(canonical(core))}
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, 'ab') as stream:
                stream.write(canonical(row))
                stream.flush()
                os.fsync(stream.fileno())
            return row


def _worker_identity(worker: TrustedFinalWorker, cell: dict,
                     ratification: dict) -> None:
    value = evidence.exact(worker.identity, {
        'schema', 'cell_id', 'source_snapshot_sha256', 'runtime_sha256',
        'action_contract_sha256', 'verifier_sha256',
        'adapter_source_sha256', 'action_profile',
        'observation_kind', 'actor_capability', 'evaluator_isolated',
        'cold_reset_supported', 'saved_state_readback_supported',
    }, 'trusted final worker identity')
    bindings = cell['matched_bindings']
    require(value == {
        'schema': WORKER_SCHEMA, 'cell_id': cell['cell_id'],
        'source_snapshot_sha256': bindings['source_snapshot'],
        'runtime_sha256': bindings['runtime'],
        'action_contract_sha256': bindings['action_contract'],
        'verifier_sha256': bindings['verifier'],
        'adapter_source_sha256':
            ratification['cell_profiles'][cell['cell_id']]['adapter_sha256'],
        'action_profile': 'scale-action-profile-v0.6.6',
        'observation_kind': 'screenshot',
        'actor_capability': 'current_frame_gui_actions_only',
        'evaluator_isolated': True, 'cold_reset_supported': True,
        'saved_state_readback_supported': True,
    } and callable(worker.run_once), 'trusted_cell_worker_contract_mismatch')


class FinalController:
    """Sequential unique-checkpoint task dispatch with durable private proof."""

    def __init__(self, gate: FinalGate, *, workers: dict[str, TrustedFinalWorker],
                 sampler_bindings_path: Path, output_dir: Path,
                 now: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic):
        require(type(gate) is FinalGate, 'validated_final_gate_required')
        self.gate, self.now, self.monotonic = gate, now, monotonic
        require(type(workers) is dict and set(workers) == set(matrix.CELLS),
                'six_trusted_cell_workers_required')
        self.cells = {row['cell_id']: row for row in gate.plan['cells']}
        for cell_id, worker in workers.items():
            _worker_identity(worker, self.cells[cell_id],
                             gate.frozen.ratification)
        self.workers = workers
        self.sampler_bindings_path = Path(sampler_bindings_path).resolve()
        bindings, bindings_raw = private_json(self.sampler_bindings_path,
                                              gate.work_root,
                                              'sampler_bindings')
        self.sampler_bindings_sha256 = sha(bindings_raw)
        require(set(bindings) == {'schema', 'study_id', 'matrix_plan_sha256',
                                  'owners'} and
                bindings['schema'] == 'cua-full-study-final-sampler-bindings-v1' and
                bindings['study_id'] == gate.plan['study_id'] and
                bindings['matrix_plan_sha256'] == gate.plan_sha256 and
                type(bindings['owners']) is list,
                'sampler_bindings_invalid')
        self.sampler_paths = {}
        expected_owners = {(cell_id, owner)
                           for cell_id, cell in self.cells.items()
                           for owner in set(cell['execution_evidence_owner_by_slot'].values())}
        for row in bindings['owners']:
            require(type(row) is dict and set(row) == {
                'cell_id', 'owner_slot', 'checkpoint_sha256', 'sampler_path',
                'observed_base_model', 'action_profile'},
                'sampler_owner_invalid')
            key = row['cell_id'], row['owner_slot']
            require(key in expected_owners and key not in self.sampler_paths,
                    'sampler_owner_unknown_or_duplicate')
            cell = self.cells[key[0]]
            slot = cell['base'] if key[1] == 'shared-base' else cell['researcher_plans'][key[1]]
            checkpoint = slot['bindings']['checkpoint']
            sampler_path = row['sampler_path']
            require(row['checkpoint_sha256'] == checkpoint and
                    row['observed_base_model'] == matrix.STUDENT and
                    row['action_profile'] == 'scale-action-profile-v0.6.6' and
                    ((key[1] == 'shared-base' and sampler_path is None) or
                     (key[1] != 'shared-base' and type(sampler_path) is str and
                      SAMPLER_PATH.fullmatch(sampler_path) is not None and
                      sha(sampler_path.encode()) == checkpoint)),
                    'sampler_checkpoint_binding_invalid')
            self.sampler_paths[key] = sampler_path
        require(set(self.sampler_paths) == expected_owners,
                'all_unique_checkpoint_sampler_bindings_required')
        self.output_dir = Path(output_dir).resolve()
        require(not self.output_dir.is_symlink() and
                self.output_dir.parent.resolve().is_relative_to(gate.work_root.resolve()),
                'private_final_output_directory_required')
        self.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.output_dir.chmod(0o700)
        self.operation_lock = self.output_dir / '.final-operation.lock'
        header = {'schema': JOURNAL_SCHEMA, 'kind': 'header',
                  'study_id': gate.plan['study_id'],
                  'matrix_plan_sha256': gate.plan_sha256,
                  'completion_index_sha256': gate.completion_index_sha256,
                  'public_final_witness_sha256': gate.public_final_witness_sha256,
                  'retry_rule_sha256': RETRY_RULE_SHA256,
                  'sampler_bindings_sha256': self.sampler_bindings_sha256}
        self.journal = FinalJournal(self.output_dir / 'final-attempts.jsonl', header)

    def _verify_frozen_inputs(self) -> None:
        require(sha(self.gate.matrix_manifest_path.read_bytes()) ==
                self.gate.plan['matrix_manifest_sha256'] and
                sha((self.gate.prepared_matrix_dir /
                     'matrix-plan.json').read_bytes()) ==
                self.gate.plan_sha256 and
                sha(self.gate.frozen.manifest_path.read_bytes()) ==
                self.gate.frozen.manifest_sha256 and
                sha(self.gate.completion_index_path.read_bytes()) ==
                self.gate.completion_index_sha256 and
                sha(self.sampler_bindings_path.read_bytes()) ==
                self.sampler_bindings_sha256,
                'frozen_final_dispatch_input_changed')

    @contextmanager
    def _locked(self):
        require(not self.output_dir.is_symlink() and
                self.output_dir.resolve().is_relative_to(
                    self.gate.work_root.resolve()) and
                not self.operation_lock.is_symlink(),
                'final_private_directory_or_lock_unsafe')
        with self.operation_lock.open('a') as lock:
            os.chmod(lock.name, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX)
            yield

    def _task_order(self, cell_id: str, owner: str) -> list[dict]:
        cell = self.cells[cell_id]
        require(owner in set(cell['execution_evidence_owner_by_slot'].values()),
                'unowned_checkpoint_execution')
        return [task for chunk in cell['base']['chunks'] for task in chunk['tasks']]

    def _reservation(self, cell_id: str, owner: str, task_id: str) -> str:
        cell_entry = next(row for row in self.gate.manifest['cells']
                          if row['cell_id'] == cell_id)
        ref = (cell_entry['base_manifest'] if owner == 'shared-base' else
               cell_entry['selected_manifests'][owner])
        manifest, _, _ = matrix._json_reference(
            self.gate.matrix_manifest_path.parent, ref, 'slot cost manifest')
        cost = manifest['cost']
        per_task = evidence.amount(cost['task_usd_upper_bound'], 'task cost')
        chunk_cost = evidence.amount(cost['chunk_usd_upper_bound'], 'chunk cost')
        slot = self.cells[cell_id]['base'] if owner == 'shared-base' else self.cells[cell_id]['researcher_plans'][owner]
        first = {chunk['tasks'][0]['task_id'] for chunk in slot['chunks']}
        return str(per_task + (chunk_cost if task_id in first else Decimal(0)))

    def _task_events(self, cell_id: str, owner: str, task_id: str) -> list[dict]:
        return [row for row in self.journal.rows()[1:]
                if row['data'].get('cell_id') == cell_id and
                row['data'].get('owner_slot') == owner and
                row['data'].get('task_id') == task_id]

    def _validate_outcome(self, outcome: object, command: dict,
                          attempt_dir: Path, elapsed_ms: int) -> tuple[dict, dict]:
        value = evidence.exact(outcome, {
            'schema', 'status', 'score', 'failure_type', 'started_at',
            'finished_at', 'cost_basis', 'cost_usd', 'usage', 'reset',
            'saved_state', 'verifier', 'observation_trace', 'action_trace',
            'action_count', 'turn_count', 'wall_time_ms',
            'provider_latency_ms', 'timeout_subtype', 'action_profile',
        }, 'trusted worker outcome')
        require(value['schema'] == OUTCOME_SCHEMA and
                value['status'] in {'scored', 'invalid'} and
                type(value['started_at']) is int and
                type(value['finished_at']) is int and
                self.gate.last_selection_frozen_at < value['started_at'] <=
                value['finished_at'] <= int(self.now()) and
                value['cost_basis'] in {'provider_billed', 'published_rate_nominal'} and
                value['action_profile'] == 'scale-action-profile-v0.6.6' and
                all(type(value[name]) is int and value[name] >= 0 for name in (
                    'action_count', 'turn_count', 'wall_time_ms',
                    'provider_latency_ms')) and
                value['action_count'] <= command['max_actions'] and
                value['turn_count'] <= command['max_actions'] + 1 and
                value['action_count'] <= value['turn_count'] and
                value['wall_time_ms'] <= command['max_wall_seconds'] * 1000 and
                value['wall_time_ms'] <= elapsed_ms + 1000 and
                value['provider_latency_ms'] <= value['wall_time_ms'],
                'worker_outcome_policy_or_time_invalid')
        cost = results.actual_usd(value['cost_usd'], 'final task cost')
        usage_path, usage_raw = private_reference(attempt_dir, value['usage'],
                                                   'provider_usage')
        usage = json.loads(usage_raw)
        require(type(usage) is dict and set(usage) == {
                    'schema', 'attempt_id', 'cost_basis', 'cost_usd',
                    'input_tokens', 'image_tokens', 'output_tokens',
                    'provider_billed_tokens', 'provider_invoice_sha256'} and
                usage['schema'] == USAGE_SCHEMA and
                usage['attempt_id'] == command['attempt_id'] and
                usage['cost_basis'] == value['cost_basis'] and
                usage['cost_usd'] == value['cost_usd'] and
                all(type(usage[key]) is int and usage[key] >= 0
                    for key in ('input_tokens', 'image_tokens', 'output_tokens')) and
                usage['image_tokens'] <= usage['input_tokens'] and
                (usage['provider_billed_tokens'] is None or
                 (type(usage['provider_billed_tokens']) is int and
                  usage['provider_billed_tokens'] >= 0)) and
                ((value['cost_basis'] == 'provider_billed' and
                  evidence.is_hash(usage['provider_invoice_sha256'])) or
                 (value['cost_basis'] == 'published_rate_nominal' and
                  usage['provider_invoice_sha256'] is None)),
                'provider_usage_receipt_invalid')
        reset_path, reset_raw = private_reference(attempt_dir, value['reset'],
                                                   'cold_reset')
        reset = json.loads(reset_raw)
        require(reset == {'schema': RESET_SCHEMA,
                          'task_id': command['task_id'],
                          'package_sha256': command['package_sha256'],
                          'attempt_id': command['attempt_id'],
                          'fresh_environment': True,
                          'restored_after_attempt': True,
                          'initial_state_sha256':
                              command['expected_initial_state_sha256'],
                          'restored_state_sha256':
                              command['expected_initial_state_sha256']},
                'cold_reset_receipt_invalid')
        observations_path, observations_raw = private_reference(
            attempt_dir, value['observation_trace'], 'observation_trace')
        actions_path, actions_raw = private_reference(
            attempt_dir, value['action_trace'], 'action_trace')
        observations = json.loads(observations_raw)
        actions = json.loads(actions_raw)
        require(observations == {'schema': TRACE_SCHEMA,
                                 'attempt_id': command['attempt_id'],
                                 'kind': 'observations',
                                 'action_profile': 'scale-action-profile-v0.6.6',
                                 'count': value['turn_count'],
                                 'screenshot_only': True} and
                actions == {'schema': TRACE_SCHEMA,
                            'attempt_id': command['attempt_id'],
                            'kind': 'actions',
                            'action_profile': 'scale-action-profile-v0.6.6',
                            'count': value['action_count'],
                            'current_frame_validated': True},
                'screenshot_action_trace_contract_invalid')
        if value['status'] == 'invalid':
            require(value['score'] is None and
                    value['failure_type'] in results.FAILURE_TYPES and
                    value['timeout_subtype'] == value['failure_type'] and
                    value['saved_state'] is None and value['verifier'] is None,
                    'invalid_infrastructure_attempt_misclassified')
            state_sha = verifier_sha = None
        else:
            require(type(value['score']) is int and value['score'] in (0, 1) and
                    value['failure_type'] is None and
                    value['timeout_subtype'] in {'none', 'actor_action_budget',
                                                 'actor_wall_budget'} and
                    (value['timeout_subtype'] == 'none' or value['score'] == 0),
                    'scored_model_attempt_invalid')
            state_path, state_raw = private_reference(attempt_dir,
                                                       value['saved_state'], 'saved_state')
            verifier_path, verifier_raw = private_reference(attempt_dir,
                                                             value['verifier'], 'verifier')
            verifier = json.loads(verifier_raw)
            require(type(verifier) is dict and set(verifier) == {
                        'schema', 'task_id', 'package_sha256', 'attempt_id',
                        'saved_state_sha256', 'score',
                        'no_regression_checked', 'no_regression_passed',
                        'independent_of_actor', 'gold_withheld_from_actor'} and
                    verifier['schema'] == VERIFIER_SCHEMA and
                    verifier['task_id'] == command['task_id'] and
                    verifier['package_sha256'] == command['package_sha256'] and
                    verifier['attempt_id'] == command['attempt_id'] and
                    verifier['saved_state_sha256'] == sha(state_raw) and
                    verifier['score'] == value['score'] and
                    verifier['no_regression_checked'] is True and
                    type(verifier['no_regression_passed']) is bool and
                    (value['score'] == 0 or
                     verifier['no_regression_passed'] is True) and
                    verifier['independent_of_actor'] is True and
                    verifier['gold_withheld_from_actor'] is True,
                    'independent_saved_state_verifier_invalid')
            state_sha, verifier_sha = sha(state_raw), sha(verifier_raw)
        require(cost <= results.actual_usd(command['reserve_usd'],
                                           'reserved final cost'),
                'final_provider_cost_exceeds_reserved_envelope')
        metric = {
            'attempt_id': command['attempt_id'],
            'attempt_receipt_sha256': None,
            'timeout_subtype': value['timeout_subtype'],
            'action_count': value['action_count'],
            'wall_time_ms': value['wall_time_ms'],
            'provider_latency_ms': value['provider_latency_ms'],
            'telemetry_trace_sha256': sha(canonical({
                'usage': sha(usage_raw), 'observations': sha(observations_raw),
                'actions': sha(actions_raw), 'reset': sha(reset_raw)})),
            'retry_provenance': None,
        }
        checked = {'value': value, 'cost': cost, 'cost_basis': value['cost_basis'],
                   'usage_sha256': sha(usage_raw), 'reset_sha256': sha(reset_raw),
                   'observation_sha256': sha(observations_raw),
                   'action_sha256': sha(actions_raw),
                   'saved_state_sha256': state_sha,
                   'verifier_sha256': verifier_sha,
                   'artifact_refs': {name: value[name] for name in (
                       'usage', 'reset', 'saved_state', 'verifier',
                       'observation_trace', 'action_trace')},
                   'metric': metric}
        return checked, {'usage': usage_path, 'reset': reset_path,
                         'observations': observations_path, 'actions': actions_path}

    def _attempt(self, cell_id: str, owner: str, task: dict,
                 retry_index: int, prior: dict | None) -> tuple[dict, dict, dict]:
        slot = (self.cells[cell_id]['base'] if owner == 'shared-base' else
                self.cells[cell_id]['researcher_plans'][owner])
        require(int(self.now()) > self.gate.last_selection_frozen_at,
                'all_selection_freezes_must_precede_paid_final_dispatch')
        execution = slot['execution']
        attempt_id = f'final-{matrix.CELLS.index(cell_id):02d}-{owner}-{self._task_order(cell_id, owner).index(task):03d}-{retry_index}'
        reserve = self._reservation(cell_id, owner, task['task_id'])
        require(Decimal(reserve) > 0, 'final_task_reserve_must_be_positive')
        command = {
            'schema': COMMAND_SCHEMA, 'study_id': self.gate.plan['study_id'],
            'cell_id': cell_id, 'owner_slot': owner,
            'task_id': task['task_id'], 'package_sha256': task['package_sha256'],
            'checkpoint_sha256': slot['bindings']['checkpoint'],
            'sampler_path': self.sampler_paths[(cell_id, owner)],
            'expected_initial_state_sha256':
                self.gate.initial_state_by_task[cell_id][task['task_id']],
            'attempt_id': attempt_id, 'retry_index': retry_index,
            'retry_rule_sha256': RETRY_RULE_SHA256 if retry_index else None,
            'action_profile': 'scale-action-profile-v0.6.6',
            'sampling': slot['sampling'],
            'max_actions': execution['max_actions_per_task'],
            'max_wall_seconds': execution['max_wall_seconds_per_task'],
            'matched_bindings': self.cells[cell_id]['matched_bindings'],
            'reserve_usd': reserve,
        }
        require(prior is None if retry_index == 0 else
                prior['status'] == 'invalid' and
                prior['failure_type'] in results.FAILURE_TYPES,
                'retry_requires_preserved_infrastructure_failure')
        attempt_dir = self.output_dir / attempt_id
        require(not attempt_dir.exists() and not attempt_dir.is_symlink(),
                'attempt_directory_already_exists_no_replay')
        attempt_dir.mkdir(mode=0o700)
        dollar_owner = f'{cell_id}:{owner}'
        category = 'shared_base_final' if owner == 'shared-base' else 'selected_final'
        self.gate.budget.reserve(attempt_id, dollar_owner, category,
                                 reserve, sha(canonical(command)))
        self.journal.append('attempt_intent', {
            'cell_id': cell_id, 'owner_slot': owner, 'task_id': task['task_id'],
            'attempt_id': attempt_id, 'command_sha256': sha(canonical(command)),
            'reserve_usd': reserve, 'retry_index': retry_index,
        })
        self.gate.budget.mark_dispatched(attempt_id, sha(canonical(command)))
        started = self.monotonic()
        try:
            outcome = self.workers[cell_id].run_once(command, attempt_dir)
            elapsed_ms = max(0, int((self.monotonic() - started) * 1000))
            checked, _ = self._validate_outcome(outcome, command,
                                                 attempt_dir, elapsed_ms)
        except BaseException:
            # A callback may have performed work or incurred cost. Never
            # auto-replay it as a fresh attempt after an exception/crash.
            self.gate.budget.mark_uncertain(attempt_id, 'transport')
            self.journal.append('attempt_uncertain', {
                'cell_id': cell_id, 'owner_slot': owner,
                'task_id': task['task_id'], 'attempt_id': attempt_id,
                'failure_type': 'transport',
            })
            raise
        self.gate.budget.settle(attempt_id, outcome['cost_usd'],
                                checked['usage_sha256'])
        attempt_receipt = {
            'schema': ATTEMPT_SCHEMA, 'cell_id': cell_id, 'owner_slot': owner,
            'task_id': task['task_id'], 'package_sha256': task['package_sha256'],
            'checkpoint_sha256': slot['bindings']['checkpoint'],
            'attempt_id': attempt_id, 'status': outcome['status'],
            'score': outcome['score'], 'failure_type': outcome['failure_type'],
            'started_at': outcome['started_at'],
            'finished_at': outcome['finished_at'],
            'usage_receipt_sha256': checked['usage_sha256'],
            'saved_state_sha256': checked['saved_state_sha256'],
            'verifier_receipt_sha256': checked['verifier_sha256'],
            'reset_receipt_sha256': checked['reset_sha256'],
            'observation_trace_sha256': checked['observation_sha256'],
            'action_trace_sha256': checked['action_sha256'],
            'cost_basis': checked['cost_basis'],
            'cost_usd': str(checked['cost']),
            'artifact_refs': checked['artifact_refs'],
        }
        receipt_path = attempt_dir / 'attempt-receipt.private.json'
        private_write_new(receipt_path, evidence.json_bytes(attempt_receipt))
        attempt = {'attempt_id': attempt_id, 'status': outcome['status'],
                   'score': outcome['score'], 'failure_type': outcome['failure_type'],
                   'started_at': outcome['started_at'],
                   'finished_at': outcome['finished_at'],
                   'receipt_sha256': sha(receipt_path.read_bytes())}
        metric = checked['metric']
        metric['attempt_receipt_sha256'] = attempt['receipt_sha256']
        if prior is not None:
            metric['retry_provenance'] = {
                'prior_attempt_id': prior['attempt_id'],
                'prior_attempt_receipt_sha256': prior['receipt_sha256'],
                'retry_rule_sha256': RETRY_RULE_SHA256,
            }
        self.journal.append('attempt_result', {
            'cell_id': cell_id, 'owner_slot': owner, 'task_id': task['task_id'],
            'attempt': attempt, 'metric': metric,
            'saved_state_sha256': checked['saved_state_sha256'],
            'verifier_receipt_sha256': checked['verifier_sha256'],
            'reset_receipt_sha256': checked['reset_sha256'],
            'observation_trace_sha256': checked['observation_sha256'],
            'action_trace_sha256': checked['action_sha256'],
            'cost_usd': str(checked['cost']), 'cost_basis': checked['cost_basis'],
        })
        return attempt, metric, checked

    def run_task(self, cell_id: str, owner: str, task_id: str) -> dict:
        """Execute a single frozen task, resuming only a reconciled invalid."""
        with self._locked():
            self._verify_frozen_inputs()
            require(cell_id in self.cells, 'unknown_cell')
            tasks = self._task_order(cell_id, owner)
            task = next((row for row in tasks if row['task_id'] == task_id), None)
            require(task is not None, 'task_not_in_frozen_final_plan')
            events = self._task_events(cell_id, owner, task_id)
            completed = [row for row in events if row['kind'] == 'task_result']
            require(len(completed) <= 1, 'duplicate_final_task_result')
            if completed:
                return completed[0]['data']['task']
            intents = [row for row in events if row['kind'] == 'attempt_intent']
            results_rows = [row for row in events if row['kind'] == 'attempt_result']
            require(len(intents) == len(results_rows) and
                    len(intents) <= 1 and
                    not any(row['kind'] == 'attempt_uncertain' for row in events),
                    'unresolved_final_attempt_no_automatic_replay')
            prior = results_rows[0]['data']['attempt'] if results_rows else None
            if prior is not None:
                require(prior['status'] == 'invalid',
                        'scored_final_attempt_missing_task_result')
            attempt, metric, checked = self._attempt(
                cell_id, owner, task, 1 if prior else 0, prior)
            attempt_rows = [prior, attempt] if prior else [attempt]
            metric_rows = ([results_rows[0]['data']['metric'], metric]
                           if prior else [metric])
            if attempt['status'] == 'invalid':
                require(prior is None, 'second_invalid_final_attempt_no_more_retries')
                return {'status': 'invalid_reconciled_retry_available',
                        'attempt_id': attempt['attempt_id']}
            final = {
                'task_id': task_id, 'package_sha256': task['package_sha256'],
                'score': attempt['score'],
                'saved_state_sha256': checked['saved_state_sha256'],
                'verifier_receipt_sha256': checked['verifier_sha256'],
                'reset_receipt_sha256': checked['reset_sha256'],
                'observation_trace_sha256': checked['observation_sha256'],
                'action_trace_sha256': checked['action_sha256'],
                'attempts': attempt_rows,
            }
            self.journal.append('task_result', {
                'cell_id': cell_id, 'owner_slot': owner, 'task_id': task_id,
                'task': final, 'metrics': metric_rows,
            })
            return final

    def run_all(self) -> dict:
        """Dispatch unique checkpoint-task pairs; exact-base reuse is implicit."""
        completed = 0
        for cell_id in matrix.CELLS:
            owners = []
            reuse = self.cells[cell_id]['execution_evidence_owner_by_slot']
            for slot in ('shared-base', *matrix.RESEARCHERS):
                owner = reuse[slot]
                if owner not in owners:
                    owners.append(owner)
            for owner in owners:
                for task in self._task_order(cell_id, owner):
                    result = self.run_task(cell_id, owner, task['task_id'])
                    if 'score' not in result:
                        # A controlled infrastructure failure is preserved;
                        # the same task gets its single retry before next task.
                        result = self.run_task(cell_id, owner, task['task_id'])
                    require('score' in result, 'final_task_not_scored')
                    completed += 1
                self.materialize_execution(cell_id, owner)
        return {'unique_checkpoint_task_executions': completed,
                'slot_task_outcomes': 3000,
                'status': 'private_execution_receipts_ready_for_audit'}

    def materialize_execution(self, cell_id: str, owner: str) -> dict:
        """Write one 100-task result and publication-compatible telemetry."""
        with self._locked():
            tasks = self._task_order(cell_id, owner)
            events = self.journal.rows()[1:]
            rows = {row['data']['task_id']: row['data'] for row in events
                    if row['kind'] == 'task_result' and
                    row['data']['cell_id'] == cell_id and
                    row['data']['owner_slot'] == owner}
            require(len(rows) == 100 and set(rows) == {task['task_id'] for task in tasks},
                    'final_execution_requires_100_scored_tasks')
            slot = (self.cells[cell_id]['base'] if owner == 'shared-base' else
                    self.cells[cell_id]['researcher_plans'][owner])
            task_results = [rows[task['task_id']]['task'] for task in tasks]
            attempts = [attempt for task in task_results for attempt in task['attempts']]
            attempt_ids = {attempt['attempt_id'] for attempt in attempts}
            costs = [row['data'] for row in events if row['kind'] == 'attempt_result'
                     and row['data']['cell_id'] == cell_id and
                     row['data']['owner_slot'] == owner]
            require(len(costs) == len(attempts) and
                    {row['attempt']['attempt_id'] for row in costs} == attempt_ids,
                    'final_execution_attempt_cost_coverage_incomplete')
            dollar_owner = f'{cell_id}:{owner}'
            billed = self.gate.budget.owner_attempts(dollar_owner)
            require(all(row['status'] in ('settled', 'cancelled')
                        for row in billed.values()),
                    'final_execution_provider_usage_unreconciled')
            for row in costs:
                attempt = row['attempt']
                attempt_dir = self.output_dir / attempt['attempt_id']
                receipt_path = attempt_dir / 'attempt-receipt.private.json'
                require(attempt_dir.is_dir() and not attempt_dir.is_symlink() and
                        receipt_path.is_file() and not receipt_path.is_symlink() and
                        receipt_path.stat().st_mode & 0o077 == 0 and
                        receipt_path.stat().st_size <= MAX_PRIVATE_BYTES,
                        'final_attempt_receipt_missing_or_unsafe')
                raw = receipt_path.read_bytes()
                require(sha(raw) == attempt['receipt_sha256'],
                        'final_attempt_receipt_changed')
                receipt = json.loads(raw)
                require(receipt['schema'] == ATTEMPT_SCHEMA and
                        receipt['attempt_id'] == attempt['attempt_id'] and
                        receipt['task_id'] in rows and
                        receipt['cost_usd'] == row['cost_usd'] and
                        receipt['cost_basis'] == row['cost_basis'] and
                        billed[attempt['attempt_id']]['status'] == 'settled' and
                        Decimal(billed[attempt['attempt_id']]['actual_usd']) ==
                            Decimal(row['cost_usd']) and
                        billed[attempt['attempt_id']]['evidence_sha256'] ==
                            receipt['usage_receipt_sha256'],
                        'final_attempt_budget_or_identity_changed')
                ref_names = {
                    'usage': 'usage_receipt_sha256',
                    'reset': 'reset_receipt_sha256',
                    'saved_state': 'saved_state_sha256',
                    'verifier': 'verifier_receipt_sha256',
                    'observation_trace': 'observation_trace_sha256',
                    'action_trace': 'action_trace_sha256',
                }
                for name, digest_name in ref_names.items():
                    artifact = receipt['artifact_refs'][name]
                    if artifact is None:
                        require(receipt[digest_name] is None,
                                'final_attempt_artifact_missing')
                    else:
                        _, artifact_raw = private_reference(
                            attempt_dir, artifact, name)
                        require(sha(artifact_raw) == receipt[digest_name],
                                'final_attempt_artifact_changed')
            cost = sum((results.actual_usd(row['cost_usd'], 'attempt cost')
                        for row in costs), Decimal(0))
            basis = ('provider_billed' if all(row['cost_basis'] == 'provider_billed'
                                              for row in costs) else
                     'published_rate_nominal')
            receipt = {
                'schema': 'cua-full-study-final-execution-v1',
                'cell_id': cell_id, 'owner_slot': owner,
                'checkpoint_sha256': slot['bindings']['checkpoint'],
                'status': 'complete',
                'started_at': min(row['started_at'] for row in attempts),
                'finished_at': max(row['finished_at'] for row in attempts),
                'cost_basis': basis, 'cost_usd': str(cost),
                'tasks': task_results,
            }
            last_freeze = max(self.gate.freezes[(cell_id, rid)]['selection_frozen_at']
                              for rid in matrix.RESEARCHERS)
            results._execution(receipt, cell_id=cell_id, owner=owner,
                               checkpoint=slot['bindings']['checkpoint'],
                               packages=results._task_packages(self.cells[cell_id]['base']),
                               after_time=last_freeze)
            owner_dir = self.output_dir / f'{cell_id}-{owner}'
            require(not owner_dir.is_symlink(),
                    'final_execution_output_symlink')
            owner_dir.mkdir(mode=0o700, exist_ok=True)
            result_path = owner_dir / 'final-execution.private.json'
            telemetry_path = owner_dir / 'final-telemetry.private.json'
            result_raw = evidence.json_bytes(receipt)
            if result_path.exists():
                require(not result_path.is_symlink() and
                        result_path.read_bytes() == result_raw,
                        'final_execution_receipt_changed')
            else:
                private_write_new(result_path, result_raw)
            telemetry = {
                'schema': 'cua-full-study-execution-telemetry-v1',
                'cell_id': cell_id, 'owner_slot': owner,
                'execution_receipt_sha256': sha(result_raw),
                'tasks': [{'task_id': task['task_id'],
                           'attempts': rows[task['task_id']]['metrics']}
                          for task in tasks],
            }
            telemetry_raw = evidence.json_bytes(telemetry)
            if telemetry_path.exists():
                require(not telemetry_path.is_symlink() and
                        telemetry_path.read_bytes() == telemetry_raw,
                        'final_telemetry_receipt_changed')
            else:
                private_write_new(telemetry_path, telemetry_raw)
            return {'cell_id': cell_id, 'owner_slot': owner,
                    'final_execution': reference(self.gate.work_root, result_path),
                    'telemetry': reference(self.gate.work_root, telemetry_path)}
