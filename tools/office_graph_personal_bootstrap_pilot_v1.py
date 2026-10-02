"""Train-only personal OneDrive pilot that can unlock the first file lease.

This is evaluator-owned and explicitly invoked. It first checks exact source,
owner, actor, drive and denied parent/sentinel with Graph reads. One invited
permission and its exact deletion use the existing hash-chained one-shot lease
state machine; ambiguous writes only permit read-only reconciliation. A
closed pilot produces the short-lived capability and source readback consumed
by `OneFileGraphLease`. No selection/final item or model call is admitted.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

from native_desktop_factory.v066_final_freeze import validate_ratification
from tools import office_graph_one_file_lease_v1 as lease
from tools import office_web_e2b_train_runner_v1 as ppt_reader
from tools import excel_web_e2b_train_runner_v1 as excel_reader
from tools.office_web_ppt_graph_readback_v1 import GraphOwnerReadback
from tools.office_web_excel_graph_readback_v1 import ExcelGraphOwnerReadback


SPEC_SCHEMA = 'cua-office-graph-personal-bootstrap-spec-v1'
PILOT_SCHEMA = 'cua-office-graph-personal-bootstrap-v1'
PROOF_SCHEMA = 'cua-office-graph-train-pilot-proof-v1'
_NAME = re.compile(
    r'EL-(?:PPT|Excel)-Train-[A-Za-z0-9._-]{1,100}\.(?:pptx|xlsx)\Z')


def _source(root: Path, reference: object, cell_id: str) -> tuple[Path, str]:
    lease._require(type(reference) is dict and
                   set(reference) == {'path', 'sha256'} and
                   type(reference['path']) is str and
                   type(reference['sha256']) is str and
                   lease._HEX.fullmatch(reference['sha256']),
                   'graph_pilot_source_reference_invalid')
    path = root / reference['path']
    lease._require(not path.is_symlink() and path.is_file() and
                   path.resolve().is_relative_to(root.resolve()) and
                   path.stat().st_mode & 0o077 == 0 and
                   path.stat().st_size <= 50_000_000,
                   'graph_pilot_source_private_file_required')
    raw = path.read_bytes()
    lease._require(lease._sha(raw) == reference['sha256'],
                   'graph_pilot_source_bytes_changed')
    try:
        if cell_id == 'powerpoint-web':
            lease._require(path.suffix == '.pptx',
                           'graph_pilot_source_kind_invalid')
            ppt_reader.readback_pptx(raw)
        else:
            lease._require(path.suffix == '.xlsx',
                           'graph_pilot_source_kind_invalid')
            excel_reader.readback_xlsx(raw)
    except ValueError:
        raise lease.GraphLeaseError(
            'graph_pilot_source_package_invalid') from None
    return path, reference['sha256']


def _load_spec(path: Path, root: Path) -> tuple[dict, str]:
    spec, raw = lease._private_json(path, root, 'graph_pilot_spec')
    fields = {'schema', 'cell_id', 'split', 'task_package_sha256',
              'source_seed_sha256', 'action_ratification_sha256',
              'owner_user_id', 'actor_user_id', 'owner_email',
              'actor_email', 'drive_id', 'item_id', 'parent_item_id',
              'sentinel_item_id', 'expected_name', 'ratification_ref',
              'source_ref', 'scope_receipt_ref',
              'hidden_final_model_attempts'}
    lease._require(set(spec) == fields and
                   spec['schema'] == SPEC_SCHEMA and
                   spec['cell_id'] in {'powerpoint-web', 'excel-web'} and
                   spec['split'] == 'train' and
                   spec['hidden_final_model_attempts'] == 0 and
                   all(type(spec[name]) is str and
                       lease._HEX.fullmatch(spec[name]) for name in (
                           'task_package_sha256', 'source_seed_sha256',
                           'action_ratification_sha256')) and
                   all(type(spec[name]) is str and
                       lease._ID.fullmatch(spec[name]) for name in (
                           'owner_user_id', 'actor_user_id', 'drive_id',
                           'item_id', 'parent_item_id',
                           'sentinel_item_id')) and
                   len({spec['item_id'], spec['parent_item_id'],
                        spec['sentinel_item_id']}) == 3 and
                   spec['owner_user_id'] != spec['actor_user_id'] and
                   all(type(spec[name]) is str and
                       lease._EMAIL.fullmatch(spec[name]) for name in (
                           'owner_email', 'actor_email')) and
                   spec['owner_email'].casefold() !=
                   spec['actor_email'].casefold() and
                   type(spec['expected_name']) is str and
                   _NAME.fullmatch(spec['expected_name']) and
                   spec['expected_name'].startswith(
                       'EL-PPT-' if spec['cell_id'] ==
                       'powerpoint-web' else 'EL-Excel-') and
                   spec['expected_name'].endswith(
                       '.pptx' if spec['cell_id'] ==
                       'powerpoint-web' else '.xlsx'),
                   'graph_pilot_spec_identity_or_train_scope_invalid')
    rat, rat_sha = lease._reference(
        root, spec['ratification_ref'], 'graph_pilot_ratification')
    try:
        validated, verified_sha = validate_ratification(
            root / spec['ratification_ref']['path'])
    except (ValueError, OSError, TypeError, KeyError):
        raise lease.GraphLeaseError(
            'graph_pilot_six_cell_ratification_invalid') from None
    lease._require(validated == rat and
                   verified_sha == rat_sha ==
                   spec['action_ratification_sha256'] and
                   spec['cell_id'] in rat['cell_profiles'],
                   'graph_pilot_action_ratification_changed')
    source_path, source_sha = _source(root, spec['source_ref'],
                                     spec['cell_id'])
    lease._require(source_sha == spec['source_seed_sha256'],
                   'graph_pilot_source_seed_hash_changed')
    scopes, scope_sha = lease._reference(
        root, spec['scope_receipt_ref'], 'graph_pilot_oauth_scope')
    lease._require(set(scopes) == {
        'schema', 'status', 'source', 'owner_user_id', 'actor_user_id',
        'owner_token_sha256', 'actor_token_sha256',
        'owner_delegated_scopes', 'actor_delegated_scopes',
        'recorded_at_utc', 'expires_at_utc'} and
        scopes['schema'] ==
            'cua-office-graph-delegated-scope-observation-v1' and
        scopes['status'] == 'observed_in_oauth_client_token_response' and
        scopes['source'] == 'evaluator_private_oauth_client' and
        scopes['owner_user_id'] == spec['owner_user_id'] and
        scopes['actor_user_id'] == spec['actor_user_id'] and
        type(scopes['owner_token_sha256']) is str and
        lease._HEX.fullmatch(scopes['owner_token_sha256']) and
        type(scopes['actor_token_sha256']) is str and
        lease._HEX.fullmatch(scopes['actor_token_sha256']) and
        type(scopes['owner_delegated_scopes']) is list and
        type(scopes['actor_delegated_scopes']) is list and
        'Files.ReadWrite' in scopes['owner_delegated_scopes'] and
        'Files.Read' in scopes['actor_delegated_scopes'] and
        all(type(value) is str for value in
            scopes['owner_delegated_scopes'] +
            scopes['actor_delegated_scopes']) and
        lease._time(scopes['recorded_at_utc']) <=
            datetime.now(timezone.utc) <
            lease._time(scopes['expires_at_utc']),
        'graph_pilot_delegated_scope_observation_missing_or_invalid')
    return {**spec, '_ratification_sha256': rat_sha,
            '_source_path': source_path,
            '_scope_receipt': scopes,
            '_scope_receipt_sha256': scope_sha}, lease._sha(raw)


def _ref(root: Path, path: Path) -> dict:
    return {'path': path.resolve().relative_to(root.resolve()).as_posix(),
            'sha256': lease._sha(path.read_bytes())}


class PrivateGraphTraceTransport:
    """Retain authenticated Graph responses privately without bearer tokens."""

    def __init__(self, inner, directory: Path, spec_sha256: str,
                 owner_token_sha256: str,
                 actor_token_sha256: str):
        self.inner = inner
        self.owner_token_sha256 = owner_token_sha256
        self.actor_token_sha256 = actor_token_sha256
        self.journal = lease.HashJournal(
            directory / 'graph-http.private.jsonl',
            {'schema': lease.JOURNAL_SCHEMA,
             'kind': 'header',
             'trace_schema':
                 'cua-office-graph-bootstrap-http-trace-v1',
             'spec_sha256': spec_sha256})

    def _role(self, token: str) -> str:
        digest = lease._sha(token)
        lease._require(digest in {self.owner_token_sha256,
                                  self.actor_token_sha256},
                       'graph_pilot_http_unknown_token')
        return ('owner' if digest == self.owner_token_sha256
                else 'actor')

    def _record(self, method: str, url: str, token: str,
                status: int, body: dict | None) -> None:
        lease._require(type(status) is int and
                       (body is None or type(body) is dict),
                       'graph_pilot_http_response_invalid')
        self.journal.append('http_observed', {
            'method': method, 'url': url,
            'token_role': self._role(token),
            'status_code': status,
            'body': body,
        })

    def get(self, url: str, token: str) -> tuple[int, dict]:
        self._role(token)
        code, body = self.inner.get(url, token)
        self._record('GET', url, token, code, body)
        return code, body

    def post(self, url: str, token: str,
             payload: dict) -> tuple[int, dict]:
        self._role(token)
        code, body = self.inner.post(url, token, payload)
        self._record('POST', url, token, code, body)
        return code, body

    def delete(self, url: str, token: str) -> int:
        self._role(token)
        code = self.inner.delete(url, token)
        self._record('DELETE', url, token, code, None)
        return code


class PersonalGraphBootstrapPilot(lease.OneFileGraphLease):
    """Use the proven one-shot Graph write protocol without a prior receipt."""

    def __init__(self, spec_path: Path, directory: Path, *,
                 work_root: Path, transport=None, source_reader=None):
        self.work_root = Path(work_root).resolve()
        self.spec, self.spec_sha256 = _load_spec(
            Path(spec_path), self.work_root)
        self.directory = Path(directory).absolute()
        lease._require(not self.directory.is_symlink() and
                       self.directory.resolve().is_relative_to(
                           self.work_root) and
                       self.directory != self.work_root,
                       'graph_pilot_private_directory_required')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.transport = PrivateGraphTraceTransport(
            transport or lease.GraphTransport(), self.directory,
            self.spec_sha256,
            self.spec['_scope_receipt']['owner_token_sha256'],
            self.spec['_scope_receipt']['actor_token_sha256'])
        self.source_reader = source_reader or (
            GraphOwnerReadback() if self.spec['cell_id'] ==
            'powerpoint-web' else ExcelGraphOwnerReadback())
        self.operation_lock_path = self.directory / '.operation.lock'
        self.journal = lease.HashJournal(
            self.directory / 'events.private.jsonl',
            {'schema': lease.JOURNAL_SCHEMA, 'kind': 'header',
             'pilot_schema': PILOT_SCHEMA,
             'spec_sha256': self.spec_sha256,
             'ratification_sha256':
                 self.spec['_ratification_sha256'],
             'scope_receipt_sha256':
                 self.spec['_scope_receipt_sha256'],
             'source_seed_sha256':
                 self.spec['source_seed_sha256'],
             'cell_id': self.spec['cell_id'],
             'split': 'train'})
        self._source_phase = None

    def _tokens(self) -> tuple[str, str]:
        owner, actor = super()._tokens()
        observed = self.spec['_scope_receipt']
        lease._require(lease._sha(owner) ==
                       observed['owner_token_sha256'] and
                       lease._sha(actor) ==
                       observed['actor_token_sha256'] and
                       lease._time(observed['recorded_at_utc']) <=
                       datetime.now(timezone.utc) <
                       lease._time(observed['expires_at_utc']),
                       'graph_pilot_tokens_do_not_match_scope_observation')
        return owner, actor

    def _source_readback(self, phase: str) -> dict:
        location = self.directory / ('source-' + phase)
        lease._require(not location.exists(),
                       'graph_pilot_source_readback_already_dispatched')
        location.mkdir(mode=0o700)
        self.source_reader.preflight()
        receipt = self.source_reader.capture(
            owner_user_id=self.spec['owner_user_id'],
            drive_id=self.spec['drive_id'],
            item_id=self.spec['item_id'],
            expected_name=self.spec['expected_name'],
            out_dir=location)
        suffix = '.pptx' if self.spec['cell_id'] == \
            'powerpoint-web' else '.xlsx'
        first = location / ('first.private' + suffix)
        second = location / ('second.private' + suffix)
        persisted, persisted_raw = lease._private_json(
            location / 'readback.private.json', self.work_root,
            'graph_pilot_owner_double_download')
        lease._require(type(receipt) is dict and receipt == persisted and
                       receipt.get('schema') == (
                           'cua-office-ppt-owner-double-download-v1'
                           if suffix == '.pptx' else
                           'cua-office-excel-owner-double-download-v1') and
                       receipt.get('owner_user_id_sha256') ==
                           lease._sha(self.spec['owner_user_id']) and
                       receipt.get('drive_id_sha256') ==
                           lease._sha(self.spec['drive_id']) and
                       receipt.get('item_id_sha256') ==
                           lease._sha(self.spec['item_id']) and
                       receipt.get('name_sha256') ==
                           lease._sha(self.spec['expected_name']) and
                       receipt.get('first_sha256') ==
                           receipt.get('second_sha256') ==
                           self.spec['source_seed_sha256'] and
                       first.is_file() and second.is_file() and
                       not first.is_symlink() and
                       not second.is_symlink() and
                       first.read_bytes() == second.read_bytes() ==
                           self.spec['_source_path'].read_bytes(),
                       'graph_pilot_owner_source_readback_changed')
        return {'receipt_sha256': lease._sha(persisted_raw),
                'source_sha256': receipt['first_sha256'],
                'item_id_sha256': receipt['item_id_sha256'],
                'phase': phase}

    def _verify_prewrite_scope(self, owner_token: str,
                               actor_token: str) -> dict:
        scope = super()._verify_prewrite_scope(owner_token,
                                                actor_token)
        lease._require(self._source_phase in {'check', 'invite'},
                       'graph_pilot_source_phase_missing')
        source = self._source_readback(self._source_phase)
        return {**scope,
                'owner_source_double_download_sha256':
                    source['receipt_sha256']}

    def check(self) -> dict:
        """Read-only account/ACL/source preflight, before any invite intent."""
        with self._operation_lock():
            lease._require(self.state() == 'prepared' and
                           not self._events(),
                           'graph_pilot_check_already_recorded')
            owner, actor = self._tokens()
            self._source_phase = 'check'
            checked = self._verify_prewrite_scope(owner, actor)
            self.journal.append('pilot_check_passed', {
                **checked,
                'epoch_seconds': int(datetime.now(
                    timezone.utc).timestamp())})
            return {'state': 'checked_train_only',
                    'source_sha256': self.spec['source_seed_sha256'],
                    'provider_write_calls': 0}

    def invite(self) -> dict:
        checked = [row for row in self._events()
                   if row['kind'] == 'pilot_check_passed']
        lease._require(len(checked) == 1 and
                       self.state() == 'prepared' and
                       int(datetime.now(timezone.utc).timestamp()) -
                       checked[0]['data']['epoch_seconds'] <= 300,
                       'graph_pilot_fresh_readonly_check_required')
        self._source_phase = 'invite'
        return super().invite()

    def abort_delete_uncertain_grant(self) -> dict:
        """Explicitly revoke one observed grant when active scope did not pass."""
        with self._operation_lock():
            lease._require(self.state() == 'invite_uncertain' and
                           not any(row['kind'] == 'active_verified' for row
                                   in self._events()),
                           'graph_pilot_abort_requires_uncertain_invite')
            owner, actor = self._tokens()
            rows = self._permission_rows(self.spec['item_id'], owner)
            candidates = self._actor_candidates(rows)
            lease._require(len(candidates) == 1,
                           'graph_pilot_abort_exact_actor_grant_unresolved')
            permission_id = self._validate_new_permission(candidates[0])
            permission = self._persist_permission(permission_id)
            endpoint = (self._url() + '/permissions/' +
                        quote(permission_id, safe=''))
            request_raw = lease._canonical({
                'method': 'DELETE', 'endpoint': endpoint,
                'permission_id': permission_id,
                'purpose': 'abort_uncertain_pilot_grant'})
            self.journal.append('delete_intent', {
                'request_sha256': lease._sha(request_raw),
                'permission_id_sha256': lease._sha(permission_id),
                'abort_only': True,
                'permission_file_sha256': permission['sha256'],
            })
            lease._write_new(self.directory /
                             'delete-request.private.json',
                             request_raw)
            try:
                status = self.transport.delete(endpoint, owner)
                lease._require(status == 204,
                               'graph_pilot_abort_delete_ambiguous')
                self.journal.append('delete_accepted', {
                    'status_code': 204,
                    'permission_id_sha256':
                        lease._sha(permission_id),
                    'abort_only': True,
                })
                closed = self._verify_closed(owner, actor)
                self.journal.append('closed_verified', closed)
                self.journal.append('pilot_aborted', {
                    'permission_id_sha256':
                        lease._sha(permission_id),
                    'capability_issued': False,
                })
                return {'state': 'closed_without_capability',
                        'permission_id_sha256':
                            lease._sha(permission_id),
                        'provider_write_calls': 1}
            except Exception as exc:
                self.journal.append('delete_uncertain', {
                    'failure_type': type(exc).__name__,
                    'request_sha256': lease._sha(request_raw),
                    'abort_only': True,
                })
                raise lease.GraphLeaseError(
                    'graph_pilot_abort_delete_uncertain_reconcile_read_only')

    def finalize(self) -> dict:
        """Produce private proofs and a ready *train-only* next-lease spec."""
        with self._operation_lock():
            lease._require(self.state() == 'closed' and
                           not any(row['kind'] == 'pilot_aborted' for row
                                   in self._events()) and
                           not (self.directory /
                                'capability.private.json').exists(),
                           'graph_pilot_closed_unfinalized_required')
            owner, actor = self._tokens()
            closed = self._verify_closed(owner, actor)
            source = self._source_readback('final')
            permission = self._permission_file()
            events = self._events()
            def unique(kind: str) -> dict:
                rows = [row for row in events if row['kind'] == kind]
                lease._require(len(rows) == 1,
                               'graph_pilot_journal_stage_missing')
                return rows[0]['data']
            check = unique('pilot_check_passed')
            invite_intent = unique('invite_intent')
            delete_intent = unique('delete_intent')
            active = unique('active_verified')
            invite_responses = [row['data'] for row in events if
                                row['kind'] in ('invite_accepted',
                                                'invite_reconciled_active')]
            lease._require(len(invite_responses) == 1,
                           'graph_pilot_active_invite_proof_missing')
            now = datetime.now(timezone.utc)
            stamp = now.isoformat()
            common = {
                'schema': PROOF_SCHEMA,
                'status': 'passed_authenticated_graph',
                'owner_user_id': self.spec['owner_user_id'],
                'actor_user_id': self.spec['actor_user_id'],
                'drive_id': self.spec['drive_id'],
                'source_split': 'train',
                'observed_at_utc': stamp,
                'hidden_final_model_attempts': 0,
            }
            permission_sha = lease._sha(permission['permission_id'])
            proof_specs = {
                'owner_token_scope': (
                    self.spec['_scope_receipt']
                        ['owner_delegated_scopes'],
                    lease._sha(lease._canonical({
                        'method': 'GET', 'path': '/me',
                        'principal': 'owner'})),
                    check['owner_identity_sha256'], None, False),
                'actor_token_scope': (
                    self.spec['_scope_receipt']
                        ['actor_delegated_scopes'],
                    lease._sha(lease._canonical({
                        'method': 'GET', 'path': '/me',
                        'principal': 'actor'})),
                    check['actor_identity_sha256'], None, False),
                'silent_invite': (
                    [], invite_intent['request_sha256'],
                    invite_responses[0].get(
                        'response_sha256',
                        lease._sha(lease._canonical(active))),
                    permission_sha, False),
                'exact_delete': (
                    [], delete_intent['request_sha256'],
                    lease._sha(lease._canonical(closed)),
                    permission_sha, False),
                'actor_scope': (
                    [], lease._sha(lease._canonical({
                        'actor_item': self.spec['item_id'],
                        'parent': self.spec['parent_item_id'],
                        'sentinel': self.spec['sentinel_item_id']})),
                    lease._sha(lease._canonical(active)),
                    None, True),
            }
            refs = {}
            for stage, (scopes, request_sha, response_sha,
                        permission_id_sha, scope_passed) in \
                    proof_specs.items():
                proof = {**common, 'stage': stage,
                         'observed_scopes': scopes,
                         'request_sha256': request_sha,
                         'response_sha256': response_sha,
                         'permission_id_sha256': permission_id_sha,
                         'target_parent_sentinel_scope_passed':
                             scope_passed}
                path = self.directory / f'pilot-{stage}.private.json'
                lease._write_new(path, lease._canonical(proof))
                refs[stage] = _ref(self.work_root, path)
            capability = {
                'schema': lease.CAPABILITY_SCHEMA,
                'status': 'verified_train_only_account_pilot',
                'owner_user_id': self.spec['owner_user_id'],
                'actor_user_id': self.spec['actor_user_id'],
                'owner_email_sha256': lease._sha(
                    self.spec['owner_email'].casefold()),
                'actor_email_sha256': lease._sha(
                    self.spec['actor_email'].casefold()),
                'drive_id': self.spec['drive_id'],
                'drive_type': 'personal',
                'owner_delegated_scopes': self.spec['_scope_receipt']
                    ['owner_delegated_scopes'],
                'actor_delegated_scopes': self.spec['_scope_receipt']
                    ['actor_delegated_scopes'],
                'silent_personal_invite_verified': True,
                'exact_delete_verified': True,
                'actor_target_and_sentinel_verified': True,
                'pilot_receipts': refs,
                'recorded_at_utc': stamp,
                'expires_at_utc': (now + timedelta(hours=24)).isoformat(),
                'hidden_final_model_attempts': 0,
            }
            cap_path = self.directory / 'capability.private.json'
            lease._write_new(cap_path, lease._canonical(capability))
            readback = {
                'schema': 'cua-office-owner-item-source-readback-v1',
                'drive_id_sha256': lease._sha(self.spec['drive_id']),
                'item_id_sha256': lease._sha(self.spec['item_id']),
                'name_sha256': lease._sha(self.spec['expected_name']),
                'source_seed_sha256': source['source_sha256'],
                'owner_user_id_sha256':
                    lease._sha(self.spec['owner_user_id']),
                'readback_passed': True,
            }
            readback_path = (self.directory /
                             'item-readback.private.json')
            lease._write_new(readback_path,
                             lease._canonical(readback))
            next_spec = {key: self.spec[key] for key in (
                'cell_id', 'split', 'task_package_sha256',
                'source_seed_sha256', 'action_ratification_sha256',
                'owner_user_id', 'actor_user_id', 'owner_email',
                'actor_email', 'drive_id', 'item_id', 'parent_item_id',
                'sentinel_item_id', 'expected_name',
                'ratification_ref')}
            next_spec.update({
                'schema': lease.SPEC_SCHEMA,
                'capability_ref': _ref(self.work_root, cap_path),
                'item_readback_ref':
                    _ref(self.work_root, readback_path),
            })
            next_path = (self.directory /
                         'ready-train-lease-spec.private.json')
            lease._write_new(next_path,
                             lease._canonical(next_spec))
            self.journal.append('pilot_finalized', {
                'capability_sha256': lease._sha(cap_path.read_bytes()),
                'item_readback_sha256':
                    lease._sha(readback_path.read_bytes()),
                'ready_train_spec_sha256':
                    lease._sha(next_path.read_bytes()),
                'permission_id_sha256': permission_sha,
            })
            return {'state': 'train_capability_ready',
                    'capability_sha256':
                        lease._sha(cap_path.read_bytes()),
                    'ready_train_spec_sha256':
                        lease._sha(next_path.read_bytes()),
                    'provider_write_calls_in_pilot': 2,
                    'selection_or_final_admitted': False}

    def prepare_matching_reset_copy(self,
                                    copy_binding_path: Path) -> dict:
        """Read-only exact-source proof for one distinct neutral train copy."""
        with self._operation_lock():
            lease._require(self.state() == 'closed' and
                           (self.directory /
                            'capability.private.json').is_file() and
                           any(row['kind'] == 'pilot_finalized' for row in
                               self._events()),
                           'graph_pilot_capability_required_for_reset_copy')
            copy, copy_raw = lease._private_json(
                copy_binding_path, self.work_root,
                'graph_pilot_reset_copy_binding')
            lease._require(set(copy) == {
                'schema', 'cell_id', 'split', 'item_id',
                'parent_item_id', 'sentinel_item_id',
                'expected_name', 'task_package_sha256',
                'source_seed_sha256', 'official_final_credit'} and
                copy['schema'] ==
                    'cua-office-graph-matching-train-reset-copy-v1' and
                copy['cell_id'] == self.spec['cell_id'] and
                copy['split'] == 'train' and
                copy['official_final_credit'] == 0 and
                all(type(copy[key]) is str and
                    lease._ID.fullmatch(copy[key]) for key in (
                        'item_id', 'parent_item_id',
                        'sentinel_item_id')) and
                copy['item_id'] not in {
                    self.spec['item_id'], self.spec['parent_item_id']} and
                copy['parent_item_id'] ==
                    self.spec['parent_item_id'] and
                copy['sentinel_item_id'] == self.spec['item_id'] and
                type(copy['expected_name']) is str and
                _NAME.fullmatch(copy['expected_name']) and
                copy['expected_name'] !=
                    self.spec['expected_name'] and
                copy['expected_name'].startswith(
                    'EL-PPT-' if self.spec['cell_id'] ==
                    'powerpoint-web' else 'EL-Excel-') and
                copy['expected_name'].endswith(
                    '.pptx' if self.spec['cell_id'] ==
                    'powerpoint-web' else '.xlsx') and
                copy['task_package_sha256'] ==
                    self.spec['task_package_sha256'] and
                copy['source_seed_sha256'] ==
                    self.spec['source_seed_sha256'],
                'graph_pilot_reset_copy_not_distinct_same_source_train')
            output = self.directory / 'matching-reset-copy'
            lease._require(not output.exists(),
                           'graph_pilot_reset_copy_already_prepared')
            output.mkdir(mode=0o700)
            owner, actor = self._tokens()
            base = ('https://graph.microsoft.com/v1.0/drives/' +
                    quote(self.spec['drive_id'], safe='') + '/items/')
            def get(url: str, token: str) -> dict:
                status, result = self.transport.get(url, token)
                lease._require(status == 200 and
                               type(result) is dict,
                               'graph_pilot_reset_owner_read_failed')
                return result
            owner_me = get('https://graph.microsoft.com/v1.0/me',
                           owner)
            actor_me = get('https://graph.microsoft.com/v1.0/me',
                           actor)
            lease._require(owner_me.get('id') ==
                           self.spec['owner_user_id'] and
                           actor_me.get('id') ==
                           self.spec['actor_user_id'],
                           'graph_pilot_reset_principal_changed')
            drive = get('https://graph.microsoft.com/v1.0/drives/' +
                        quote(self.spec['drive_id'], safe=''), owner)
            drive_owner = drive.get('owner')
            lease._require(drive.get('id') == self.spec['drive_id'] and
                           drive.get('driveType') == 'personal' and
                           type(drive_owner) is dict and
                           type(drive_owner.get('user')) is dict and
                           drive_owner['user'].get('id') ==
                           self.spec['owner_user_id'],
                           'graph_pilot_reset_drive_changed')
            item = get(base + quote(copy['item_id'], safe=''), owner)
            parent = item.get('parentReference')
            lease._require(item.get('id') == copy['item_id'] and
                           item.get('name') == copy['expected_name'] and
                           type(item.get('file')) is dict and
                           type(parent) is dict and
                           parent.get('driveId') ==
                           self.spec['drive_id'] and
                           parent.get('id') ==
                           copy['parent_item_id'],
                           'graph_pilot_reset_exact_item_changed')
            for item_id in (copy['item_id'],
                            copy['parent_item_id']):
                permissions = get(base + quote(item_id, safe='') +
                                  '/permissions', owner)
                lease._require(permissions.get('@odata.nextLink')
                               is None and
                               type(permissions.get('value')) is list,
                               'graph_pilot_reset_permissions_invalid')
                GraphOwnerReadback._revoked_permissions(
                    permissions['value'],
                    owner_user_id=self.spec['owner_user_id'],
                    actor_email=self.spec['actor_email'],
                    prior_permission_id='__none__')
            for item_id in (copy['item_id'],
                            copy['parent_item_id'],
                            copy['sentinel_item_id']):
                status, _ = self.transport.get(
                    base + quote(item_id, safe=''), actor)
                lease._require(status in (403, 404),
                               'graph_pilot_reset_actor_scope_too_broad')
            readback_dir = output / 'owner-readback'
            readback_dir.mkdir(mode=0o700)
            self.source_reader.preflight()
            receipt = self.source_reader.capture(
                owner_user_id=self.spec['owner_user_id'],
                drive_id=self.spec['drive_id'],
                item_id=copy['item_id'],
                expected_name=copy['expected_name'],
                out_dir=readback_dir)
            suffix = '.pptx' if self.spec['cell_id'] == \
                'powerpoint-web' else '.xlsx'
            first = readback_dir / ('first.private' + suffix)
            second = readback_dir / ('second.private' + suffix)
            persisted, _ = lease._private_json(
                readback_dir / 'readback.private.json',
                self.work_root,
                'graph_pilot_reset_owner_double_download')
            lease._require(receipt == persisted and
                           receipt.get('schema') == (
                               'cua-office-ppt-owner-double-download-v1'
                               if suffix == '.pptx' else
                               'cua-office-excel-owner-double-download-v1')
                           and
                           receipt.get('owner_user_id_sha256') ==
                           lease._sha(self.spec['owner_user_id']) and
                           receipt.get('drive_id_sha256') ==
                           lease._sha(self.spec['drive_id']) and
                           receipt.get('item_id_sha256') ==
                           lease._sha(copy['item_id']) and
                           receipt.get('name_sha256') ==
                           lease._sha(copy['expected_name']) and
                           receipt.get('first_sha256') ==
                           receipt.get('second_sha256') ==
                           self.spec['source_seed_sha256'] and
                           first.read_bytes() == second.read_bytes() ==
                               self.spec['_source_path'].read_bytes(),
                           'graph_pilot_reset_source_readback_changed')
            readback = {
                'schema': 'cua-office-owner-item-source-readback-v1',
                'drive_id_sha256': lease._sha(self.spec['drive_id']),
                'item_id_sha256': lease._sha(copy['item_id']),
                'name_sha256': lease._sha(copy['expected_name']),
                'source_seed_sha256': self.spec['source_seed_sha256'],
                'owner_user_id_sha256':
                    lease._sha(self.spec['owner_user_id']),
                'readback_passed': True,
            }
            readback_path = (output /
                             'item-readback.private.json')
            lease._write_new(readback_path,
                             lease._canonical(readback))
            ready = {key: self.spec[key] for key in (
                'cell_id', 'split', 'task_package_sha256',
                'source_seed_sha256', 'action_ratification_sha256',
                'owner_user_id', 'actor_user_id', 'owner_email',
                'actor_email', 'drive_id', 'ratification_ref')}
            ready.update({
                'schema': lease.SPEC_SCHEMA,
                'item_id': copy['item_id'],
                'parent_item_id': copy['parent_item_id'],
                'sentinel_item_id': copy['sentinel_item_id'],
                'expected_name': copy['expected_name'],
                'capability_ref': _ref(
                    self.work_root,
                    self.directory / 'capability.private.json'),
                'item_readback_ref':
                    _ref(self.work_root, readback_path),
            })
            spec_path = output / 'ready-reset-lease-spec.private.json'
            lease._write_new(spec_path, lease._canonical(ready))
            self.journal.append('matching_reset_copy_prepared', {
                'copy_binding_sha256': lease._sha(copy_raw),
                'item_readback_sha256':
                    lease._sha(readback_path.read_bytes()),
                'ready_reset_spec_sha256':
                    lease._sha(spec_path.read_bytes()),
                'provider_write_calls': 0,
            })
            return {'state': 'train_reset_copy_ready',
                    'ready_reset_spec_sha256':
                        lease._sha(spec_path.read_bytes()),
                    'provider_write_calls': 0}
