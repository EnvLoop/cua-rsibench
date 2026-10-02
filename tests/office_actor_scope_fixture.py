"""Synthetic, offline-only evidence for actor-scope gate tests."""

from __future__ import annotations

from pathlib import Path
import time

from tools import office_web_actor_scope_gate_v1 as scope_gate
from tools import office_web_e2b_login_bridge_v1 as bridge


OWNER = 'owner@example.test'
ACTOR = 'actor@example.test'
ASSIGNED = 'DEMO!101'
PARENT = 'DEMO!100'


def write_scope_fixture(session_path: Path, session: dict, item_url: str,
                        app: str, actor_seed_sha256: str, png: bytes) -> dict:
    """Never use this fixture as live Microsoft permission evidence."""
    directory = session_path.parent
    directory.chmod(0o700)
    owner_hash = scope_gate.digest(OWNER)
    actor_hash = scope_gate.digest(ACTOR)
    now = int(time.time())
    for name in scope_gate._EVIDENCE_NAMES:
        path = directory / f'{name}.private.png'
        path.unlink(missing_ok=True)
        path.write_bytes(png)
        path.chmod(0o600)
    assigned = {
        'schema': scope_gate.SNAPSHOT_SCHEMA,
        'owner_principal_sha256': owner_hash,
        'item_id': ASSIGNED, 'http_status': 200,
        'response': {'value': [{
            'id': 'synthetic-permission-1', 'roles': ['write'],
            'invitation': {'email': ACTOR, 'signInRequired': True},
        }]},
    }
    parent = {
        'schema': scope_gate.SNAPSHOT_SCHEMA,
        'owner_principal_sha256': owner_hash,
        'item_id': PARENT, 'http_status': 200,
        'response': {'value': []},
    }
    for name, payload in (('assigned-permissions', assigned),
                          ('parent-permissions', parent)):
        path = directory / f'{name}.private.json'
        path.unlink(missing_ok=True)
        bridge.write_new(path, payload)
    receipt = {
        'schema': scope_gate.SCHEMA,
        'app': app, 'split': 'train', 'status': 'operator_reviewed',
        'observed_at_unix': now,
        'valid_until_unix': min(now + 240,
                                session['lease_started_at_unix'] +
                                session['lease_seconds']),
        'session_sha256': scope_gate.digest(session_path.read_bytes()),
        'sandbox_id_sha256': scope_gate.digest(session['sandbox_id']),
        'assigned_url_sha256': scope_gate.digest(item_url),
        'owner_email': OWNER, 'actor_email': ACTOR,
        'owner_principal_sha256': owner_hash,
        'actor_principal_sha256': actor_hash,
        'assigned_item_id': ASSIGNED, 'parent_item_id': PARENT,
        'actor_seed_sha256': actor_seed_sha256,
        'owner_permissions': {
            'file': 'assigned-permissions.private.json',
            'sha256': scope_gate.digest(
                (directory / 'assigned-permissions.private.json').read_bytes()),
        },
        'parent_permissions': {
            'file': 'parent-permissions.private.json',
            'sha256': scope_gate.digest(
                (directory / 'parent-permissions.private.json').read_bytes()),
        },
        'evidence': {name: {
            'file': f'{name}.private.png',
            'sha256': scope_gate.digest(png),
        } for name in scope_gate._EVIDENCE_NAMES},
        'reviews': {
            'distinct_accounts': True,
            'actor_signed_in_as_actor': True,
            'assigned_file_editable': True,
            'sentinel_file_denied': True,
            'owner_seed_readback_matched': True,
            'no_other_benchmark_item_visible': True,
        },
    }
    path = directory / 'actor-scope.private.json'
    path.unlink(missing_ok=True)
    bridge.write_new(path, receipt)
    return receipt
