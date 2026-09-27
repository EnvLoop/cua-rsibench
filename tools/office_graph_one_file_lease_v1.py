"""Evaluator-only Microsoft Graph single-file actor permission lease.

No model or GUI actor receives a Graph endpoint or bearer token. A real write
requires an evaluator-private capability receipt from a prior bounded train
pilot, distinct delegated owner/actor tokens, exact item/source bindings, and
read-only account/ACL probes. Invitation and deletion are one-shot: their
exact intent is fsynced before POST/DELETE and an ambiguous response is never
automatically replayed. Reconciliation is read-only.

No live account-capability receipt is shipped with this repository.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Callable
from urllib.parse import quote

from tools.office_web_ppt_graph_readback_v1 import GraphOwnerReadback


SCHEMA = 'cua-office-graph-one-file-lease-v1'
SPEC_SCHEMA = 'cua-office-graph-one-file-spec-v1'
CAPABILITY_SCHEMA = 'cua-office-graph-personal-capability-v1'
JOURNAL_SCHEMA = 'cua-office-graph-one-file-journal-v1'
_HEX = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[A-Za-z0-9!._:-]{4,180}\Z')
_EMAIL = re.compile(r'[^@\s]{1,128}@[^@\s]{1,255}\Z')
_MAX_BYTES = 2_000_000


class GraphLeaseError(ValueError):
    pass


def _require(value: bool, code: str) -> None:
    if not value:
        raise GraphLeaseError(code)


def _sha(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=False, allow_nan=False) + '\n').encode()


def _private_json(path: Path, work_root: Path, label: str) -> tuple[dict, bytes]:
    original = Path(path)
    _require(not original.is_symlink(), label + '_private_file_required')
    target = original.resolve()
    _require(target.is_file() and
             target.is_relative_to(work_root.resolve()) and
             target.stat().st_mode & 0o077 == 0 and
             0 < target.stat().st_size <= _MAX_BYTES,
             label + '_private_file_required')
    raw = target.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GraphLeaseError(label + '_invalid_json') from None
    _require(type(value) is dict, label + '_object_required')
    return value, raw


def _write_new(path: Path, raw: bytes) -> None:
    _require(not path.is_symlink() and not path.exists(),
             'graph_lease_artifact_already_exists')
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise GraphLeaseError('capability_time_invalid') from None
    _require(parsed.tzinfo is not None, 'capability_time_invalid')
    return parsed.astimezone(timezone.utc)


def _reference(root: Path, value: object, label: str) -> tuple[dict, str]:
    _require(type(value) is dict and set(value) == {'path', 'sha256'} and
             type(value['path']) is str and
             type(value['sha256']) is str and
             _HEX.fullmatch(value['sha256']) is not None,
             label + '_reference_invalid')
    path = root / value['path']
    result, raw = _private_json(path, root, label)
    _require(_sha(raw) == value['sha256'], label + '_bytes_changed')
    return result, value['sha256']


def _load_spec(spec_path: Path, work_root: Path) -> tuple[dict, str]:
    spec, raw = _private_json(spec_path, work_root, 'graph_lease_spec')
    fields = {'schema', 'cell_id', 'split', 'task_package_sha256',
              'source_seed_sha256', 'action_ratification_sha256',
              'owner_user_id', 'actor_user_id', 'owner_email', 'actor_email',
              'drive_id', 'item_id', 'parent_item_id', 'sentinel_item_id',
              'expected_name', 'ratification_ref',
              'capability_ref', 'item_readback_ref'}
    _require(set(spec) == fields and spec['schema'] == SPEC_SCHEMA and
             spec['cell_id'] in {'powerpoint-web', 'excel-web'} and
             spec['split'] in {'train', 'selection', 'final'} and
             all(type(spec[key]) is str and _HEX.fullmatch(spec[key])
                 for key in ('task_package_sha256', 'source_seed_sha256',
                             'action_ratification_sha256')) and
             all(type(spec[key]) is str and _ID.fullmatch(spec[key])
                 for key in ('owner_user_id', 'actor_user_id', 'drive_id',
                             'item_id', 'parent_item_id', 'sentinel_item_id')) and
             len({spec['item_id'], spec['parent_item_id'],
                  spec['sentinel_item_id']}) == 3 and
             spec['owner_user_id'] != spec['actor_user_id'] and
             all(type(spec[key]) is str and _EMAIL.fullmatch(spec[key])
                 for key in ('owner_email', 'actor_email')) and
             spec['owner_email'].casefold() !=
             spec['actor_email'].casefold() and
             type(spec['expected_name']) is str and
             re.fullmatch(
                 r'EL-(?:PPT|Excel)-(?:Train|Selection|Final)-[A-Za-z0-9._-]{1,100}\.(?:pptx|xlsx)',
                 spec['expected_name']) is not None and
             spec['expected_name'].startswith(
                 'EL-PPT-' if spec['cell_id'] == 'powerpoint-web' else
                 'EL-Excel-') and
             ('-Train-' if spec['split'] == 'train' else
              '-Selection-' if spec['split'] == 'selection' else '-Final-')
             in spec['expected_name'],
             'graph_lease_spec_identity_invalid')
    ratification, ratification_sha = _reference(
        work_root, spec['ratification_ref'], 'graph_action_ratification')
    from native_desktop_factory.v066_final_freeze import validate_ratification
    try:
        checked, verified_sha = validate_ratification(
            work_root / spec['ratification_ref']['path'])
    except (ValueError, OSError, KeyError, TypeError):
        raise GraphLeaseError('graph_six_cell_ratification_invalid') from None
    _require(checked == ratification and
             verified_sha == ratification_sha ==
             spec['action_ratification_sha256'] and
             spec['cell_id'] in ratification['cell_profiles'],
             'graph_six_cell_ratification_changed')
    cap, cap_sha = _reference(work_root, spec['capability_ref'],
                              'graph_capability')
    now = datetime.now(timezone.utc)
    _require(set(cap) == {
        'schema', 'status', 'owner_user_id', 'actor_user_id',
        'owner_email_sha256', 'actor_email_sha256', 'drive_id',
        'drive_type', 'owner_delegated_scopes', 'actor_delegated_scopes',
        'silent_personal_invite_verified', 'exact_delete_verified',
        'actor_target_and_sentinel_verified', 'pilot_receipts',
        'recorded_at_utc', 'expires_at_utc',
        'hidden_final_model_attempts'},
        'graph_capability_receipt_shape_invalid')
    _require(cap['schema'] == CAPABILITY_SCHEMA and
             cap['status'] == 'verified_train_only_account_pilot' and
             cap['owner_user_id'] == spec['owner_user_id'] and
             cap['actor_user_id'] == spec['actor_user_id'] and
             cap['owner_email_sha256'] ==
             _sha(spec['owner_email'].casefold()) and
             cap['actor_email_sha256'] ==
             _sha(spec['actor_email'].casefold()) and
             cap['drive_id'] == spec['drive_id'] and
             cap['drive_type'] == 'personal' and
             type(cap['owner_delegated_scopes']) is list and
             type(cap['actor_delegated_scopes']) is list and
             'Files.ReadWrite' in cap['owner_delegated_scopes'] and
             'Files.Read' in cap['actor_delegated_scopes'] and
             cap['silent_personal_invite_verified'] is True and
             cap['exact_delete_verified'] is True and
             cap['actor_target_and_sentinel_verified'] is True and
             cap['hidden_final_model_attempts'] == 0 and
             _time(cap['recorded_at_utc']) <= now <
             _time(cap['expires_at_utc']),
             'graph_personal_account_write_capability_unverified')
    stages = {'owner_token_scope', 'actor_token_scope',
              'silent_invite', 'exact_delete', 'actor_scope'}
    _require(type(cap['pilot_receipts']) is dict and
             set(cap['pilot_receipts']) == stages,
             'graph_personal_account_pilot_evidence_missing')
    pilot = {}
    for stage, reference in cap['pilot_receipts'].items():
        proof, proof_sha = _reference(work_root, reference,
                                      'graph_pilot_' + stage)
        _require(set(proof) == {
            'schema', 'stage', 'status', 'owner_user_id',
            'actor_user_id', 'drive_id', 'source_split',
            'observed_scopes', 'request_sha256',
            'response_sha256', 'permission_id_sha256',
            'target_parent_sentinel_scope_passed',
            'observed_at_utc', 'hidden_final_model_attempts'} and
            proof['schema'] == 'cua-office-graph-train-pilot-proof-v1' and
            proof['stage'] == stage and
            proof['status'] == 'passed_authenticated_graph' and
            proof['owner_user_id'] == spec['owner_user_id'] and
            proof['actor_user_id'] == spec['actor_user_id'] and
            proof['drive_id'] == spec['drive_id'] and
            proof['source_split'] == 'train' and
            type(proof['observed_scopes']) is list and
            all(type(scope) is str for scope in
                proof['observed_scopes']) and
            all(type(proof[key]) is str and _HEX.fullmatch(proof[key])
                for key in ('request_sha256', 'response_sha256')) and
            (proof['permission_id_sha256'] is None or
             type(proof['permission_id_sha256']) is str and
             _HEX.fullmatch(proof['permission_id_sha256'])) and
            type(proof['target_parent_sentinel_scope_passed']) is bool and
            proof['hidden_final_model_attempts'] == 0 and
            _time(proof['observed_at_utc']) <=
            _time(cap['recorded_at_utc']) <= now and
            (_time(cap['recorded_at_utc']) -
             _time(proof['observed_at_utc'])).total_seconds() <=
             30 * 24 * 3600,
            'graph_personal_account_pilot_evidence_invalid')
        pilot[stage] = (proof, proof_sha)
    _require('Files.ReadWrite' in pilot['owner_token_scope'][0]
             ['observed_scopes'] and
             'Files.Read' in pilot['actor_token_scope'][0]
             ['observed_scopes'] and
             pilot['silent_invite'][0]['permission_id_sha256'] is not None and
             pilot['silent_invite'][0]['permission_id_sha256'] ==
             pilot['exact_delete'][0]['permission_id_sha256'] and
             pilot['actor_scope'][0]
             ['target_parent_sentinel_scope_passed'] is True,
             'graph_personal_account_pilot_chain_incomplete')
    readback, readback_sha = _reference(
        work_root, spec['item_readback_ref'], 'graph_source_readback')
    _require(readback == {
        'schema': 'cua-office-owner-item-source-readback-v1',
        'drive_id_sha256': _sha(spec['drive_id']),
        'item_id_sha256': _sha(spec['item_id']),
        'name_sha256': _sha(spec['expected_name']),
        'source_seed_sha256': spec['source_seed_sha256'],
        'owner_user_id_sha256': _sha(spec['owner_user_id']),
        'readback_passed': True,
    }, 'graph_exact_item_source_readback_missing')
    return {**spec, '_capability_sha256': cap_sha,
            '_ratification_sha256': ratification_sha,
            '_item_readback_sha256': readback_sha}, _sha(raw)


class GraphTransport:
    """No automatic write retries or redirect following for Graph mutations."""

    def __init__(self, client_factory: Callable | None = None):
        self.client_factory = client_factory

    @contextmanager
    def _client(self):
        if self.client_factory is not None:
            client = self.client_factory()
        else:
            import httpx
            client = httpx.Client(timeout=httpx.Timeout(30, connect=10),
                                  follow_redirects=False)
        try:
            yield client
        finally:
            client.close()

    def get(self, url: str, token: str) -> tuple[int, dict]:
        with self._client() as client:
            response = client.get(url, headers={
                'Authorization': 'Bearer ' + token})
            body = response.json() if response.status_code == 200 else {}
            return response.status_code, body

    def post(self, url: str, token: str, payload: dict) -> tuple[int, dict]:
        with self._client() as client:
            response = client.post(url, headers={
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json'}, json=payload)
            body = response.json() if response.status_code in (200, 207) else {}
            return response.status_code, body

    def delete(self, url: str, token: str) -> int:
        with self._client() as client:
            response = client.delete(url, headers={
                'Authorization': 'Bearer ' + token})
            return response.status_code


class HashJournal:
    def __init__(self, path: Path, header: dict):
        self.path = path
        self.header = header
        self.lock_path = path.with_name('.' + path.name + '.lock')
        if not path.exists():
            core = {**header, 'previous': None}
            _write_new(path, _canonical({**core,
                                        'hash': _sha(_canonical(core))}))
        self.rows()

    @contextmanager
    def lock(self):
        _require(not self.lock_path.is_symlink(),
                 'graph_lease_lock_symlink')
        fd = os.open(self.lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def rows(self) -> list[dict]:
        _require(self.path.is_file() and not self.path.is_symlink() and
                 self.path.stat().st_mode & 0o077 == 0,
                 'graph_lease_journal_private_required')
        try:
            rows = [json.loads(line) for line in self.path.read_bytes().splitlines()]
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise GraphLeaseError('graph_lease_journal_invalid_json') from None
        _require(bool(rows), 'graph_lease_journal_empty')
        previous = None
        for index, row in enumerate(rows):
            _require(type(row) is dict and row.get('previous') == previous,
                     'graph_lease_journal_hash_broken')
            core = {key: value for key, value in row.items()
                    if key != 'hash'}
            _require(row.get('hash') == _sha(_canonical(core)),
                     'graph_lease_journal_hash_broken')
            if index == 0:
                _require(core == {**self.header, 'previous': None},
                         'graph_lease_journal_binding_changed')
            else:
                _require(row.get('sequence') == index and
                         row.get('schema') == JOURNAL_SCHEMA,
                         'graph_lease_journal_sequence_invalid')
            previous = row['hash']
        return rows

    def append(self, kind: str, data: dict) -> dict:
        with self.lock():
            rows = self.rows()
            core = {'schema': JOURNAL_SCHEMA, 'kind': kind,
                    'sequence': len(rows), 'data': data,
                    'previous': rows[-1]['hash']}
            row = {**core, 'hash': _sha(_canonical(core))}
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND)
            with os.fdopen(fd, 'ab') as stream:
                stream.write(_canonical(row))
                stream.flush()
                os.fsync(stream.fileno())
            return row


class OneFileGraphLease:
    """One immutable owner/actor/item; no implicit retries or task switching."""

    def __init__(self, spec_path: Path, directory: Path, *,
                 work_root: Path, transport: GraphTransport | None = None):
        self.work_root = Path(work_root).resolve()
        self.spec, self.spec_sha256 = _load_spec(
            Path(spec_path), self.work_root)
        self.directory = Path(directory).absolute()
        _require(not self.directory.is_symlink() and
                 self.directory.resolve().is_relative_to(self.work_root) and
                 self.directory != self.work_root,
                 'graph_lease_requires_private_work_directory')
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        self.transport = transport or GraphTransport()
        self.operation_lock_path = self.directory / '.operation.lock'
        self.journal = HashJournal(
            self.directory / 'events.private.jsonl',
            {'schema': JOURNAL_SCHEMA, 'kind': 'header',
             'spec_sha256': self.spec_sha256,
             'capability_sha256': self.spec['_capability_sha256'],
             'source_readback_sha256': self.spec['_item_readback_sha256'],
             'cell_id': self.spec['cell_id'],
             'split': self.spec['split']})

    @contextmanager
    def _operation_lock(self):
        _require(not self.operation_lock_path.is_symlink(),
                 'graph_lease_operation_lock_symlink')
        fd = os.open(self.operation_lock_path,
                     os.O_WRONLY | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'w') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def _events(self) -> list[dict]:
        return self.journal.rows()[1:]

    def state(self) -> str:
        kinds = [row['kind'] for row in self._events()]
        if any(kind in ('closed_verified', 'closed_reconciled')
               for kind in kinds):
            return 'closed'
        if 'delete_intent' in kinds:
            return 'delete_uncertain'
        if 'active_verified' in kinds:
            return 'active'
        if 'invite_intent' in kinds:
            return 'invite_uncertain'
        return 'prepared'

    def _tokens(self) -> tuple[str, str]:
        owner = os.environ.get('MS_GRAPH_OWNER_TOKEN')
        actor = os.environ.get('MS_GRAPH_ACTOR_TOKEN')
        _require(type(owner) is str and len(owner) >= 12 and
                 type(actor) is str and len(actor) >= 12 and
                 owner != actor,
                 'graph_distinct_delegated_tokens_missing')
        return owner, actor

    def _url(self, item_id: str | None = None) -> str:
        return ('https://graph.microsoft.com/v1.0/drives/' +
                quote(self.spec['drive_id'], safe='') + '/items/' +
                quote(item_id or self.spec['item_id'], safe=''))

    def _get_json(self, url: str, token: str,
                  *, label: str) -> dict:
        code, body = self.transport.get(url, token)
        _require(code == 200 and type(body) is dict,
                 label + '_graph_read_failed')
        return body

    def _permission_rows(self, item_id: str, owner_token: str) -> list[dict]:
        body = self._get_json(self._url(item_id) + '/permissions',
                              owner_token, label='permissions')
        _require(body.get('@odata.nextLink') is None and
                 type(body.get('value')) is list and
                 len(body['value']) <= 1000,
                 'graph_permission_list_paginated_or_invalid')
        return body['value']

    def _actor_status(self, item_id: str, actor_token: str) -> int:
        code, _ = self.transport.get(self._url(item_id), actor_token)
        return code

    def _actor_deny_other_items(self, actor_token: str) -> None:
        _require(self._actor_status(self.spec['parent_item_id'], actor_token)
                 in (403, 404) and
                 self._actor_status(self.spec['sentinel_item_id'], actor_token)
                 in (403, 404),
                 'graph_actor_parent_or_sentinel_accessible')

    def _verify_prewrite_scope(self, owner_token: str,
                               actor_token: str) -> dict:
        owner = self._get_json('https://graph.microsoft.com/v1.0/me',
                               owner_token, label='owner_identity')
        actor = self._get_json('https://graph.microsoft.com/v1.0/me',
                               actor_token, label='actor_identity')
        _require(owner.get('id') == self.spec['owner_user_id'] and
                 actor.get('id') == self.spec['actor_user_id'] and
                 owner['id'] != actor['id'],
                 'graph_delegated_account_identity_changed')
        drive = self._get_json(
            'https://graph.microsoft.com/v1.0/drives/' +
            quote(self.spec['drive_id'], safe=''),
            owner_token, label='owner_drive')
        drive_owner = drive.get('owner')
        _require(drive.get('id') == self.spec['drive_id'] and
                 drive.get('driveType') == 'personal' and
                 type(drive_owner) is dict and
                 type(drive_owner.get('user')) is dict and
                 drive_owner['user'].get('id') ==
                 self.spec['owner_user_id'],
                 'graph_owner_drive_not_verified_personal')
        item = self._get_json(self._url(), owner_token,
                              label='assigned_item')
        parent = item.get('parentReference')
        _require(item.get('id') == self.spec['item_id'] and
                 item.get('name') == self.spec['expected_name'] and
                 type(item.get('file')) is dict and
                 type(parent) is dict and
                 parent.get('driveId') == self.spec['drive_id'] and
                 parent.get('id') == self.spec['parent_item_id'],
                 'graph_exact_nonroot_item_changed')
        prior = self._permission_rows(self.spec['item_id'], owner_token)
        parent_rows = self._permission_rows(
            self.spec['parent_item_id'], owner_token)
        for rows in (prior, parent_rows):
            GraphOwnerReadback._revoked_permissions(
                rows, owner_user_id=self.spec['owner_user_id'],
                actor_email=self.spec['actor_email'],
                prior_permission_id='__no_prior_grant__')
        _require(self._actor_status(self.spec['item_id'], actor_token)
                 in (403, 404),
                 'graph_actor_already_accessed_assigned_item')
        self._actor_deny_other_items(actor_token)
        return {'owner_identity_sha256': _sha(_canonical(owner)),
                'actor_identity_sha256': _sha(_canonical(actor)),
                'drive_sha256': _sha(_canonical(drive)),
                'item_sha256': _sha(_canonical(item)),
                'prior_permissions_sha256': _sha(_canonical(prior)),
                'parent_permissions_sha256': _sha(_canonical(parent_rows))}

    def _permission_file(self) -> dict:
        value, raw = _private_json(
            self.directory / 'permission.private.json',
            self.work_root, 'graph_permission')
        _require(set(value) == {'schema', 'permission_id',
                                'actor_email_sha256', 'item_id_sha256',
                                'invite_request_sha256'} and
                 value['schema'] == 'cua-office-one-file-permission-v1' and
                 type(value['permission_id']) is str and
                 1 <= len(value['permission_id']) <= 180 and
                 value['actor_email_sha256'] ==
                 _sha(self.spec['actor_email'].casefold()) and
                 value['item_id_sha256'] ==
                 _sha(self.spec['item_id']),
                 'graph_permission_file_binding_changed')
        intents = [row for row in self._events()
                   if row['kind'] == 'invite_intent']
        _require(len(intents) == 1 and
                 value['invite_request_sha256'] ==
                 intents[0]['data']['request_sha256'],
                 'graph_permission_file_invite_intent_changed')
        accepted = [row for row in self._events()
                    if row['kind'] in ('invite_accepted',
                                       'invite_reconciled_active')]
        if accepted:
            _require(len(accepted) == 1 and
                     accepted[0]['data']['permission_file_sha256'] ==
                     _sha(raw) and
                     accepted[0]['data']['permission_id_sha256'] ==
                     _sha(value['permission_id']),
                     'graph_permission_file_exact_id_changed')
        return {**value, '_sha256': _sha(raw)}

    @staticmethod
    def _is_actor_permission(row: dict, *, actor_email: str,
                             actor_user_id: str) -> bool:
        invitation = row.get('invitation')
        email_match = (type(invitation) is dict and
                       type(invitation.get('email')) is str and
                       invitation['email'].casefold() ==
                       actor_email.casefold())
        granted = row.get('grantedToV2') or row.get('grantedTo')
        id_match = (type(granted) is dict and
                    type(granted.get('user')) is dict and
                    granted['user'].get('id') == actor_user_id)
        return email_match or id_match

    def _actor_candidates(self, rows: list[dict]) -> list[dict]:
        result = []
        for row in rows:
            _require(type(row) is dict and
                     type(row.get('id')) is str and
                     type(row.get('roles')) is list,
                     'graph_permission_response_invalid')
            if self._is_actor_permission(
                    row, actor_email=self.spec['actor_email'],
                    actor_user_id=self.spec['actor_user_id']):
                result.append(row)
        return result

    def _validate_new_permission(self, row: dict) -> str:
        invitation = row.get('invitation')
        _require(type(row) is dict and
                 type(row.get('id')) is str and
                 1 <= len(row['id']) <= 180 and
                 row.get('roles') == ['write'] and
                 type(invitation) is dict and
                 invitation.get('signInRequired') is True and
                 type(invitation.get('email')) is str and
                 invitation['email'].casefold() ==
                 self.spec['actor_email'].casefold() and
                 row.get('link') is None and
                 row.get('inheritedFrom') is None,
                 'graph_invite_not_exact_specific_person_write')
        return row['id']

    def _persist_permission(self, permission_id: str) -> dict:
        intent = [row for row in self._events()
                  if row['kind'] == 'invite_intent']
        _require(len(intent) == 1,
                 'graph_invite_intent_missing')
        value = {
            'schema': 'cua-office-one-file-permission-v1',
            'permission_id': permission_id,
            'actor_email_sha256': _sha(
                self.spec['actor_email'].casefold()),
            'item_id_sha256': _sha(self.spec['item_id']),
            'invite_request_sha256': intent[0]['data']['request_sha256'],
        }
        path = self.directory / 'permission.private.json'
        if path.exists():
            existing, _ = _private_json(path, self.work_root,
                                        'graph_permission')
            _require(existing == value,
                     'graph_permission_id_changed_after_invite')
        else:
            _write_new(path, _canonical(value))
        return {**value, 'sha256': _sha(path.read_bytes())}

    def _verify_active(self, owner_token: str,
                       actor_token: str) -> dict:
        permission = self._permission_file()
        rows = self._permission_rows(self.spec['item_id'], owner_token)
        candidates = self._actor_candidates(rows)
        _require(len(candidates) == 1 and
                 candidates[0]['id'] == permission['permission_id'],
                 'graph_actor_grant_not_unique_or_changed')
        self._validate_new_permission(candidates[0])
        for row in rows:
            if row['id'] == permission['permission_id']:
                continue
            GraphOwnerReadback._revoked_permissions(
                [row], owner_user_id=self.spec['owner_user_id'],
                actor_email=self.spec['actor_email'],
                prior_permission_id=permission['permission_id'])
        _require(self._actor_status(self.spec['item_id'], actor_token) == 200,
                 'graph_actor_cannot_read_only_assigned_file')
        self._actor_deny_other_items(actor_token)
        return {'permission_id_sha256':
                    _sha(permission['permission_id']),
                'owner_permissions_sha256': _sha(_canonical(rows)),
                'actor_item_access': 200,
                'parent_and_sentinel_denied': True}

    def _verify_closed(self, owner_token: str,
                       actor_token: str) -> dict:
        permission = self._permission_file()
        rows = self._permission_rows(self.spec['item_id'], owner_token)
        audit = GraphOwnerReadback._revoked_permissions(
            rows, owner_user_id=self.spec['owner_user_id'],
            actor_email=self.spec['actor_email'],
            prior_permission_id=permission['permission_id'])
        _require(self._actor_status(self.spec['item_id'], actor_token)
                 in (403, 404),
                 'graph_actor_still_reads_revoked_item')
        self._actor_deny_other_items(actor_token)
        return {'permission_id_sha256':
                    _sha(permission['permission_id']),
                'owner_permissions_sha256': _sha(_canonical(rows)),
                'actor_item_denied': True,
                'owner_and_inherited_retained_count':
                    audit['owner_permission_count'] +
                    audit['inherited_permission_count'],
                'broad_links_remaining': 0}

    def invite(self) -> dict:
        with self._operation_lock():
            _require(self.spec['split'] == 'train',
                     'graph_selection_final_requires_separate_matrix_gate')
            _require(self.state() == 'prepared',
                     'graph_invite_already_dispatched_or_closed')
            owner_token, actor_token = self._tokens()
            preflight = self._verify_prewrite_scope(owner_token,
                                                    actor_token)
            self.journal.append('preflight_passed', preflight)
            payload = {'recipients': [
                {'email': self.spec['actor_email']}],
                'roles': ['write'], 'requireSignIn': True,
                'sendInvitation': False}
            endpoint = self._url() + '/invite'
            exact_request = {'method': 'POST', 'endpoint': endpoint,
                             'body': payload}
            request_raw = _canonical(exact_request)
            self.journal.append('invite_intent', {
                'request_sha256': _sha(request_raw),
                'target_item_id_sha256': _sha(self.spec['item_id']),
                'actor_email_sha256': _sha(
                    self.spec['actor_email'].casefold()),
            })
            _write_new(self.directory / 'invite-request.private.json',
                       request_raw)
            try:
                code, response = self.transport.post(
                    endpoint, owner_token, payload)
                _require(code == 200 and type(response) is dict and
                         type(response.get('value')) is list and
                         len(response['value']) == 1,
                         'graph_invite_response_ambiguous')
                permission_id = self._validate_new_permission(
                    response['value'][0])
                permission = self._persist_permission(permission_id)
                self.journal.append('invite_accepted', {
                    'permission_file_sha256': permission['sha256'],
                    'permission_id_sha256': _sha(permission_id),
                    'response_sha256': _sha(_canonical(response)),
                })
                active = self._verify_active(owner_token, actor_token)
                self.journal.append('active_verified', active)
                return {'state': 'active',
                        'permission_id_sha256': _sha(permission_id),
                        'actor_only_assigned_item_verified': True}
            except Exception as exc:
                self.journal.append('invite_uncertain', {
                    'failure_type': type(exc).__name__,
                    'request_sha256': _sha(request_raw),
                })
                raise GraphLeaseError(
                    'graph_invite_uncertain_read_only_reconciliation_required') from None

    def reconcile_invite(self) -> dict:
        with self._operation_lock():
            _require(self.state() == 'invite_uncertain',
                     'graph_invite_reconciliation_not_needed')
            owner_token, actor_token = self._tokens()
            rows = self._permission_rows(self.spec['item_id'], owner_token)
            candidates = self._actor_candidates(rows)
            if len(candidates) != 1:
                self.journal.append('invite_reconciliation_observed', {
                    'actor_candidate_count': len(candidates),
                    'owner_permissions_sha256': _sha(_canonical(rows)),
                })
                return {'state': 'invite_uncertain',
                        'actor_candidate_count': len(candidates),
                        'provider_write_calls': 0}
            permission_id = self._validate_new_permission(candidates[0])
            permission = self._persist_permission(permission_id)
            try:
                active = self._verify_active(owner_token, actor_token)
            except Exception:
                self.journal.append('invite_reconciliation_observed', {
                    'actor_candidate_count': 1,
                    'owner_permissions_sha256': _sha(_canonical(rows)),
                })
                return {'state': 'invite_uncertain',
                        'actor_candidate_count': 1,
                        'provider_write_calls': 0}
            self.journal.append('invite_reconciled_active', {
                'permission_file_sha256': permission['sha256'],
                **active,
            })
            # The active receipt is separately recorded so the state reducer
            # shares one unambiguous active transition with normal invite.
            self.journal.append('active_verified', active)
            return {'state': 'active',
                    'permission_id_sha256': _sha(permission_id),
                    'provider_write_calls': 0}

    def delete(self) -> dict:
        with self._operation_lock():
            _require(self.state() == 'active',
                     'graph_delete_requires_active_exact_permission')
            owner_token, actor_token = self._tokens()
            permission = self._permission_file()
            endpoint = (self._url() + '/permissions/' +
                        quote(permission['permission_id'], safe=''))
            request_raw = _canonical({'method': 'DELETE',
                                      'endpoint': endpoint,
                                      'permission_id':
                                          permission['permission_id']})
            self.journal.append('delete_intent', {
                'request_sha256': _sha(request_raw),
                'permission_id_sha256': _sha(
                    permission['permission_id']),
            })
            _write_new(self.directory / 'delete-request.private.json',
                       request_raw)
            try:
                code = self.transport.delete(endpoint, owner_token)
                _require(code == 204,
                         'graph_exact_permission_delete_ambiguous')
                self.journal.append('delete_accepted', {
                    'status_code': 204,
                    'permission_id_sha256':
                        _sha(permission['permission_id']),
                })
                closed = self._verify_closed(owner_token, actor_token)
                self.journal.append('closed_verified', closed)
                return {'state': 'closed',
                        'permission_id_sha256':
                            _sha(permission['permission_id']),
                        'actor_access_revoked': True}
            except Exception as exc:
                self.journal.append('delete_uncertain', {
                    'failure_type': type(exc).__name__,
                    'request_sha256': _sha(request_raw),
                })
                raise GraphLeaseError(
                    'graph_delete_uncertain_read_only_reconciliation_required') from None

    def reconcile_delete(self) -> dict:
        with self._operation_lock():
            _require(self.state() == 'delete_uncertain',
                     'graph_delete_reconciliation_not_needed')
            owner_token, actor_token = self._tokens()
            try:
                closed = self._verify_closed(owner_token, actor_token)
            except Exception as exc:
                self.journal.append('delete_reconciliation_observed', {
                    'failure_type': type(exc).__name__,
                    'provider_write_calls': 0,
                })
                return {'state': 'delete_uncertain',
                        'provider_write_calls': 0}
            self.journal.append('closed_reconciled', closed)
            return {'state': 'closed',
                    'permission_id_sha256': closed['permission_id_sha256'],
                    'provider_write_calls': 0}

    def snapshot(self) -> dict:
        rows = self.journal.rows()
        return {'schema': SCHEMA,
                'state': self.state(),
                'cell_id': self.spec['cell_id'],
                'split': self.spec['split'],
                'spec_sha256': self.spec_sha256,
                'event_count': len(rows) - 1,
                'journal_head_sha256': rows[-1]['hash'],
                'permission_id_sha256': (
                    _sha(self._permission_file()['permission_id']) if
                    (self.directory / 'permission.private.json').exists()
                    else None),
                'provider_write_calls_claimed': sum(
                    row['kind'] in ('invite_intent', 'delete_intent')
                    for row in rows[1:]),
                'official_task_result': None}
