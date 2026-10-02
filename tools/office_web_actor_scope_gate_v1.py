"""Offline, fail-closed admission for a one-file Office-web actor share.

This checks the shape, binding, freshness, and hashes of evaluator-private
evidence. It cannot authenticate Microsoft Graph snapshots or read screenshot
semantics by itself. A trusted evaluator must collect and review those inputs;
neither this gate nor a passing fake-provider test is a live ACL result.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time


SCHEMA = 'envloop-office-web-actor-scope-private-v1'
SNAPSHOT_SCHEMA = 'envloop-office-web-owner-permissions-snapshot-private-v1'
MAX_AGE_SECONDS = 300
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_EMAIL = re.compile(r'[^@\s]{1,128}@[^@\s]{1,255}\Z')
_ITEM_ID = re.compile(r'[A-Za-z0-9!._-]{4,160}\Z')
_EVIDENCE_NAMES = ('actor_identity', 'assigned_edit', 'sentinel_denial',
                   'owner_seed_readback')


class ScopeError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ScopeError(code)


def digest(raw: bytes | str) -> str:
    return hashlib.sha256(raw if isinstance(raw, bytes) else raw.encode()).hexdigest()


def private_root() -> Path:
    return (Path.cwd() / 'work').resolve()


def private_bytes(path: Path, *, directory: Path, maximum: int) -> bytes:
    """Never follow a symlink or read a public/worktree-tracked proof file."""
    path = Path(path).absolute()
    directory = directory.absolute()
    try:
        mode = path.stat().st_mode & 0o777
        size = path.stat().st_size
        directory_mode = directory.stat().st_mode & 0o777
    except OSError:
        raise ScopeError('private_scope_evidence_required') from None
    require('..' not in path.parts and '..' not in directory.parts and
            path.parent == directory and
            directory.is_relative_to(private_root()) and
            not path.is_symlink() and path.is_file() and
            (directory_mode & 0o077) == 0 and
            mode == 0o600 and 0 < size <= maximum,
            'private_scope_evidence_required')
    for parent in (directory, *directory.parents):
        if parent == private_root().parent:
            break
        require(not parent.is_symlink(), 'private_scope_evidence_required')
    return path.read_bytes()


def evidence_file(directory: Path, entry: object, *, name: str,
                  maximum: int = 20_000_000) -> bytes:
    require(type(entry) is dict and set(entry) == {'file', 'sha256'} and
            type(entry['file']) is str and
            entry['file'] == f'{name}.private.png' and
            type(entry['sha256']) is str and
            _HEX64.fullmatch(entry['sha256']) is not None,
            'invalid_scope_evidence_reference')
    raw = private_bytes(directory / entry['file'], directory=directory,
                        maximum=maximum)
    require(raw.startswith(b'\x89PNG\r\n\x1a\n') and
            digest(raw) == entry['sha256'],
            'scope_evidence_hash_or_format_mismatch')
    return raw


def permission_snapshot(directory: Path, entry: object, *, name: str,
                        owner_hash: str, item_id: str) -> dict:
    require(type(entry) is dict and set(entry) == {'file', 'sha256'} and
            entry.get('file') == f'{name}.private.json' and
            type(entry.get('sha256')) is str and
            _HEX64.fullmatch(entry['sha256']) is not None,
            'invalid_permission_snapshot_reference')
    raw = private_bytes(directory / entry['file'], directory=directory,
                        maximum=1_000_000)
    require(digest(raw) == entry['sha256'],
            'permission_snapshot_hash_mismatch')
    try:
        snapshot = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ScopeError('invalid_permission_snapshot') from None
    require(type(snapshot) is dict and
            set(snapshot) == {'schema', 'owner_principal_sha256', 'item_id',
                              'http_status', 'response'} and
            snapshot['schema'] == SNAPSHOT_SCHEMA and
            snapshot['owner_principal_sha256'] == owner_hash and
            snapshot['item_id'] == item_id and
            type(snapshot['http_status']) is int and
            snapshot['http_status'] == 200 and
            type(snapshot['response']) is dict and
            set(snapshot['response']) == {'value'} and
            type(snapshot['response']['value']) is list,
            'invalid_permission_snapshot')
    return snapshot['response']


def validate(scope_path: Path, *, session_raw: bytes, sandbox_id: str,
             item_url: str, app: str, lease_started_at_unix: int,
             lease_end_unix: int, actor_seed_sha256: str | None = None,
             now: int | None = None) -> dict:
    """Check a fresh owner-side file permission and operator-reviewed probes.

    This is a train-only pre-model gate. Post-run source-bound owner readback,
    permission removal, and a second actor denial probe remain separate gates.
    """
    now = int(time.time()) if now is None else now
    scope_path = Path(scope_path).absolute()
    require(scope_path.name == 'actor-scope.private.json',
            'scope_receipt_required')
    directory = scope_path.parent
    raw = private_bytes(scope_path, directory=directory, maximum=100_000)
    try:
        scope = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ScopeError('invalid_scope_receipt') from None
    require(type(scope) is dict and set(scope) == {
        'schema', 'app', 'split', 'status', 'observed_at_unix',
        'valid_until_unix', 'session_sha256', 'sandbox_id_sha256',
        'assigned_url_sha256', 'owner_email', 'actor_email',
        'owner_principal_sha256', 'actor_principal_sha256',
        'assigned_item_id', 'parent_item_id', 'actor_seed_sha256',
        'owner_permissions', 'parent_permissions', 'evidence', 'reviews',
    } and scope['schema'] == SCHEMA and scope['app'] == app and
            app in ('powerpoint', 'excel') and scope['split'] == 'train' and
            scope['status'] == 'operator_reviewed' and
            type(scope['observed_at_unix']) is int and
            type(scope['valid_until_unix']) is int and
            lease_started_at_unix <= scope['observed_at_unix'] <= now and
            now - scope['observed_at_unix'] <= MAX_AGE_SECONDS and
            now < scope['valid_until_unix'] <= lease_end_unix and
            scope['session_sha256'] == digest(session_raw) and
            scope['sandbox_id_sha256'] == digest(sandbox_id) and
            scope['assigned_url_sha256'] == digest(item_url),
            'scope_binding_or_freshness_failed')
    require(type(scope['owner_email']) is str and
            _EMAIL.fullmatch(scope['owner_email']) is not None and
            type(scope['actor_email']) is str and
            _EMAIL.fullmatch(scope['actor_email']) is not None and
            scope['owner_email'].casefold() != scope['actor_email'].casefold() and
            scope['owner_principal_sha256'] == digest(scope['owner_email'].casefold()) and
            scope['actor_principal_sha256'] == digest(scope['actor_email'].casefold()) and
            type(scope['assigned_item_id']) is str and
            _ITEM_ID.fullmatch(scope['assigned_item_id']) is not None and
            type(scope['parent_item_id']) is str and
            _ITEM_ID.fullmatch(scope['parent_item_id']) is not None and
            scope['assigned_item_id'] != scope['parent_item_id'] and
            type(scope['actor_seed_sha256']) is str and
            _HEX64.fullmatch(scope['actor_seed_sha256']) is not None and
            (actor_seed_sha256 is None or
             scope['actor_seed_sha256'] == actor_seed_sha256),
            'invalid_scope_principals_or_items')
    review_keys = {'distinct_accounts', 'actor_signed_in_as_actor',
                   'assigned_file_editable', 'sentinel_file_denied',
                   'owner_seed_readback_matched', 'no_other_benchmark_item_visible'}
    require(type(scope['reviews']) is dict and
            set(scope['reviews']) == review_keys and
            all(value is True for value in scope['reviews'].values()),
            'scope_operator_review_incomplete')
    require(type(scope['evidence']) is dict and
            set(scope['evidence']) == set(_EVIDENCE_NAMES),
            'scope_operator_evidence_incomplete')
    for name in _EVIDENCE_NAMES:
        evidence_file(directory, scope['evidence'][name], name=name)
    file_response = permission_snapshot(
        directory, scope['owner_permissions'], name='assigned-permissions',
        owner_hash=scope['owner_principal_sha256'],
        item_id=scope['assigned_item_id'])
    parent_response = permission_snapshot(
        directory, scope['parent_permissions'], name='parent-permissions',
        owner_hash=scope['owner_principal_sha256'],
        item_id=scope['parent_item_id'])
    require(parent_response['value'] == [], 'parent_folder_is_shared')
    require(len(file_response['value']) == 1,
            'assigned_file_has_extra_permissions')
    permission = file_response['value'][0]
    require(type(permission) is dict and
            type(permission.get('id')) is str and
            0 < len(permission['id']) <= 160 and
            permission.get('roles') == ['write'] and
            type(permission.get('invitation')) is dict and
            permission['invitation'].get('signInRequired') is True and
            type(permission['invitation'].get('email')) is str and
            permission['invitation']['email'].casefold() ==
            scope['actor_email'].casefold() and
            permission.get('inheritedFrom') is None and
            permission.get('link') is None,
            'assigned_file_not_single_specific_person_edit')
    return {
        'status': 'train_scope_evidence_accepted_operator_review_only',
        'receipt_sha256': digest(raw),
        'owner_permissions_sha256': scope['owner_permissions']['sha256'],
        'parent_permissions_sha256': scope['parent_permissions']['sha256'],
        'permission_id_sha256': digest(permission['id']),
        'official_final_admitted': 0,
    }
