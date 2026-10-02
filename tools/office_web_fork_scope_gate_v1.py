"""Train-only offline evidence gate for a clean Office actor desktop fork.

This validates private receipt structure and operator-provided evidence bytes.
It cannot authenticate E2B or Microsoft responses, inspect screenshot meaning,
or grant an official final-task admission.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from tools import office_web_actor_scope_gate_v1 as scope_gate


BASELINE_SCHEMA = 'envloop-office-web-fork-baseline-private-v1'
FORK_SCHEMA = 'envloop-office-web-fork-child-private-v1'
INVENTORY_SCHEMA = 'envloop-office-web-owner-actor-inventory-private-v1'
MAX_EVIDENCE_AGE_SECONDS = 300
_BASELINE_IMAGES = (
    'baseline-identity', 'baseline-local-history',
    'baseline-cloud-recent', 'baseline-cloud-shared',
)
_FORK_IMAGES = (
    'parent-cloud-recent', 'child-identity', 'child-local-history',
    'child-cloud-recent', 'child-cloud-shared',
)
_BASELINE_REVIEWS = (
    'dedicated_actor_not_owner', 'no_benchmark_files_in_parent_vm',
    'no_benchmark_file_access', 'no_benchmark_local_history',
    'no_benchmark_cloud_recent', 'no_benchmark_cloud_shared',
    'parent_stream_stopped', 'parent_vnc_access_material_absent',
)
_FORK_REVIEWS = (
    'parent_unchanged_after_previous_attempt',
    'parent_cloud_recent_has_no_benchmark_item',
    'child_desktop_usable', 'child_signed_in_as_dedicated_actor',
    'child_local_history_has_no_benchmark_item',
    'child_cloud_recent_has_no_benchmark_item',
    'child_cloud_shared_has_no_benchmark_item',
    'child_had_no_benchmark_file_before_grant',
    'one_active_grant_for_actor',
)


class ForkScopeError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def require(value: bool, code: str) -> None:
    if not value:
        raise ForkScopeError(code)


def _private_json(path: Path, *, directory: Path, maximum: int = 200_000
                  ) -> tuple[dict, bytes]:
    try:
        raw = scope_gate.private_bytes(path, directory=directory,
                                       maximum=maximum)
        value = json.loads(raw)
    except (scope_gate.ScopeError, ValueError, UnicodeError):
        raise ForkScopeError('private_fork_evidence_required') from None
    require(type(value) is dict, 'invalid_fork_evidence')
    return value, raw


def _pictures(directory: Path, evidence: object, names: tuple[str, ...]
              ) -> None:
    require(type(evidence) is dict and set(evidence) == set(names),
            'fork_visual_evidence_incomplete')
    for name in names:
        try:
            scope_gate.evidence_file(directory, evidence[name], name=name)
        except scope_gate.ScopeError:
            raise ForkScopeError('fork_visual_evidence_invalid') from None


def _reviews(value: object, names: tuple[str, ...]) -> None:
    require(type(value) is dict and set(value) == set(names) and
            all(value[name] is True for name in names),
            'fork_operator_review_incomplete')


def _inventory(directory: Path, reference: object, *, name: str,
               expected_manifest_sha256: str, expected_count: int,
               owner_sha256: str, actor_sha256: str, assigned_sha256: str | None,
               lower_time: int, upper_time: int) -> str:
    require(type(reference) is dict and set(reference) == {'file', 'sha256'} and
            reference['file'] == f'{name}.private.json' and
            type(reference['sha256']) is str and
            scope_gate._HEX64.fullmatch(reference['sha256']) is not None,
            'invalid_fork_inventory_reference')
    inventory, raw = _private_json(directory / reference['file'],
                                   directory=directory, maximum=2_000_000)
    require(scope_gate.digest(raw) == reference['sha256'] and
            set(inventory) == {
                'schema', 'source', 'complete', 'manifest_sha256',
                'captured_at_unix', 'owner_principal_sha256',
                'actor_principal_sha256', 'entries',
            } and inventory['schema'] == INVENTORY_SCHEMA and
            inventory['source'] == 'owner_authenticated_permission_sweep' and
            inventory['complete'] is True and
            inventory['manifest_sha256'] == expected_manifest_sha256 and
            type(inventory['captured_at_unix']) is int and
            lower_time <= inventory['captured_at_unix'] <= upper_time and
            inventory['owner_principal_sha256'] == owner_sha256 and
            inventory['actor_principal_sha256'] == actor_sha256 and
            type(inventory['entries']) is list and
            len(inventory['entries']) == expected_count,
            'fork_inventory_binding_failed')
    seen: set[str] = set()
    granted: set[str] = set()
    for item in inventory['entries']:
        require(type(item) is dict and
                set(item) == {'item_id_sha256', 'actor_roles'} and
                type(item['item_id_sha256']) is str and
                scope_gate._HEX64.fullmatch(item['item_id_sha256']) is not None and
                item['item_id_sha256'] not in seen and
                item['actor_roles'] in ([], ['write']),
                'fork_inventory_item_invalid')
        seen.add(item['item_id_sha256'])
        if item['actor_roles']:
            granted.add(item['item_id_sha256'])
    canonical_ids = json.dumps(sorted(seen), separators=(',', ':'))
    require(scope_gate.digest(canonical_ids) == expected_manifest_sha256,
            'fork_inventory_manifest_mismatch')
    require(granted == ({assigned_sha256} if assigned_sha256 else set()),
            'fork_actor_has_extra_or_missing_grant')
    return scope_gate.digest(raw)


def validate(baseline_path: Path, fork_path: Path, scope_path: Path, *,
             parent_session_raw: bytes, child_session_raw: bytes,
             parent_sandbox_id: str, child_sandbox_id: str,
             item_url: str, app: str,
             parent_lease_started_at_unix: int, parent_lease_end_unix: int,
             child_lease_started_at_unix: int, child_lease_end_unix: int,
             inventory_manifest_sha256: str,
             inventory_count: int, actor_seed_sha256: str | None = None,
             now: int | None = None) -> dict:
    """Check an operator-attested train fork before any model dispatch.

    The owner-authenticated sweep and screenshot meanings must be verified by
    an independent trusted collector. This offline function only checks their
    private byte bindings, shape, ordering, and conservative assertions.
    """
    now = int(time.time()) if now is None else now
    baseline_path, fork_path, scope_path = map(
        lambda p: Path(p).absolute(),
        (baseline_path, fork_path, scope_path))
    directory = fork_path.parent
    require(baseline_path.parent == directory and scope_path.parent == directory and
            baseline_path.name == 'baseline.private.json' and
            fork_path.name == 'fork.private.json' and
            scope_path.name == 'actor-scope.private.json' and
            type(inventory_manifest_sha256) is str and
            scope_gate._HEX64.fullmatch(inventory_manifest_sha256) is not None and
            type(inventory_count) is int and 2 <= inventory_count <= 10_000 and
            type(now) is int and
            type(parent_sandbox_id) is str and
            type(child_sandbox_id) is str and
            type(item_url) is str and
            all(type(value) is int for value in (
                parent_lease_started_at_unix, parent_lease_end_unix,
                child_lease_started_at_unix, child_lease_end_unix)) and
            parent_sandbox_id != child_sandbox_id and
            type(parent_session_raw) is bytes and
            type(child_session_raw) is bytes and
            parent_lease_started_at_unix <= child_lease_started_at_unix and
            now < min(parent_lease_end_unix, child_lease_end_unix),
            'invalid_fork_inputs')
    try:
        scope = scope_gate.validate(
            scope_path, session_raw=child_session_raw,
            sandbox_id=child_sandbox_id, item_url=item_url, app=app,
            lease_started_at_unix=child_lease_started_at_unix,
            lease_end_unix=child_lease_end_unix,
            actor_seed_sha256=actor_seed_sha256, now=now)
    except scope_gate.ScopeError:
        raise ForkScopeError('one_file_actor_scope_unverified') from None
    scope_body, scope_raw = _private_json(scope_path, directory=directory)
    owner_hash = scope_body['owner_principal_sha256']
    actor_hash = scope_body['actor_principal_sha256']
    assigned_hash = scope_gate.digest(scope_body['assigned_item_id'])
    baseline, baseline_raw = _private_json(baseline_path, directory=directory)
    require(set(baseline) == {
                'schema', 'split', 'status', 'prepared_at_unix',
                'valid_until_unix', 'parent_session_sha256',
                'parent_sandbox_id_sha256', 'owner_principal_sha256',
                'actor_principal_sha256', 'inventory_manifest_sha256',
                'inventory', 'reviews', 'evidence',
            } and baseline['schema'] == BASELINE_SCHEMA and
            baseline['split'] == 'train' and
            baseline['status'] == 'operator_reviewed' and
            type(baseline['prepared_at_unix']) is int and
            type(baseline['valid_until_unix']) is int and
            parent_lease_started_at_unix <= baseline['prepared_at_unix'] <= now and
            now < baseline['valid_until_unix'] <= parent_lease_end_unix and
            baseline['parent_session_sha256'] == scope_gate.digest(parent_session_raw) and
            baseline['parent_sandbox_id_sha256'] == scope_gate.digest(parent_sandbox_id) and
            baseline['owner_principal_sha256'] == owner_hash and
            baseline['actor_principal_sha256'] == actor_hash and
            baseline['inventory_manifest_sha256'] == inventory_manifest_sha256,
            'fork_baseline_binding_failed')
    _reviews(baseline['reviews'], _BASELINE_REVIEWS)
    _pictures(directory, baseline['evidence'], _BASELINE_IMAGES)
    fork, fork_raw = _private_json(fork_path, directory=directory)
    require(set(fork) == {
                'schema', 'split', 'status', 'baseline_sha256',
                'child_session_sha256', 'parent_sandbox_id_sha256',
                'child_sandbox_id_sha256', 'owner_principal_sha256',
                'actor_principal_sha256', 'assigned_item_id_sha256',
                'scope_receipt_sha256', 'forked_at_unix',
                'pregrant_observed_at_unix', 'grant_observed_at_unix',
                'inventory', 'reviews', 'evidence',
            } and fork['schema'] == FORK_SCHEMA and
            fork['split'] == 'train' and
            fork['status'] == 'operator_reviewed' and
            fork['baseline_sha256'] == scope_gate.digest(baseline_raw) and
            fork['child_session_sha256'] == scope_gate.digest(child_session_raw) and
            fork['parent_sandbox_id_sha256'] == scope_gate.digest(parent_sandbox_id) and
            fork['child_sandbox_id_sha256'] == scope_gate.digest(child_sandbox_id) and
            fork['owner_principal_sha256'] == owner_hash and
            fork['actor_principal_sha256'] == actor_hash and
            fork['assigned_item_id_sha256'] == assigned_hash and
            fork['scope_receipt_sha256'] == scope_gate.digest(scope_raw) and
            type(fork['forked_at_unix']) is int and
            type(fork['pregrant_observed_at_unix']) is int and
            type(fork['grant_observed_at_unix']) is int and
            baseline['prepared_at_unix'] <= fork['forked_at_unix'] <=
            child_lease_started_at_unix <=
            fork['pregrant_observed_at_unix'] < fork['grant_observed_at_unix'] <=
            scope_body['observed_at_unix'] <= now and
            now - fork['pregrant_observed_at_unix'] <= MAX_EVIDENCE_AGE_SECONDS,
            'fork_child_binding_or_order_failed')
    _reviews(fork['reviews'], _FORK_REVIEWS)
    _pictures(directory, fork['evidence'], _FORK_IMAGES)
    baseline_inventory_sha = _inventory(
        directory, baseline['inventory'], name='baseline-inventory',
        expected_manifest_sha256=inventory_manifest_sha256,
        expected_count=inventory_count, owner_sha256=owner_hash,
        actor_sha256=actor_hash, assigned_sha256=None,
        lower_time=baseline['prepared_at_unix'],
        upper_time=min(fork['forked_at_unix'],
                       baseline['prepared_at_unix'] + MAX_EVIDENCE_AGE_SECONDS))
    grant_inventory_sha = _inventory(
        directory, fork['inventory'], name='grant-inventory',
        expected_manifest_sha256=inventory_manifest_sha256,
        expected_count=inventory_count, owner_sha256=owner_hash,
        actor_sha256=actor_hash, assigned_sha256=assigned_hash,
        lower_time=fork['grant_observed_at_unix'],
        upper_time=scope_body['observed_at_unix'])
    require(grant_inventory_sha != baseline_inventory_sha,
            'fork_inventory_did_not_change')
    return {
        'status': 'train_fork_scope_evidence_accepted_operator_review_only',
        'baseline_sha256': scope_gate.digest(baseline_raw),
        'fork_sha256': scope_gate.digest(fork_raw),
        'scope_sha256': scope['receipt_sha256'],
        'baseline_inventory_sha256': baseline_inventory_sha,
        'grant_inventory_sha256': grant_inventory_sha,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
