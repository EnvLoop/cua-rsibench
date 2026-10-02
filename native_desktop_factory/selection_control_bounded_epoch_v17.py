"""Fresh source-only transport epoch retaining the closed v16 failure bytes."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_structural_epoch_v16 as parent
from . import selection_control_accounting_epoch_v13 as history
from . import v066_post_enter_epoch_v9 as core
from . import bounded_guest_transport_v17 as transport
from .factory import digest

SCHEMA = 'cua-native-desktop-bounded-transfer-private-v17'
PUBLIC_SCHEMA = 'cua-native-desktop-bounded-transfer-public-v17'
PERMIT_SCHEMA = 'cua-native-desktop-bounded-transfer-trio-permit-v17'
SOURCE_FILES = (*parent.SOURCE_FILES,
    'native_desktop_factory/bounded_guest_transport_v17.py',
    'native_desktop_factory/selection_control_bounded_epoch_v17.py',
    'native_desktop_factory/selection_control_bounded_worker_v17.py',
    'tests/test_desktop_bounded_transfer_v17.py')
MAX_ACTIONS = parent.MAX_ACTIONS
ACTOR_WALL_SECONDS = parent.ACTOR_WALL_SECONDS
LEASE_SECONDS = parent.LEASE_SECONDS
accounting = parent.accounting
private = parent.private
require = parent.require
ORIGINAL_ACCOUNTING = parent.ORIGINAL_ACCOUNTING
ORIGINAL_MANIFEST = parent.ORIGINAL_MANIFEST


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: digest((root / name).read_bytes()) for name in SOURCE_FILES}


@contextmanager
def parent_history(own):
    # This layer excludes only the fresh v17 descendant. v16 keeps its own
    # established exclusion while validating its closed ancestors.
    def roots(values):return [history.HistoricalRoot(root, (own.resolve(),)) for root in values]
    def projected_account(values, *, exclude=None):return ORIGINAL_ACCOUNTING(roots(values), exclude=exclude)
    def projected_manifest(values, *, exclude):return ORIGINAL_MANIFEST(roots(values), exclude=exclude)
    with patch.object(parent, 'ORIGINAL_ACCOUNTING', projected_account), \
         patch.object(parent, 'ORIGINAL_MANIFEST', projected_manifest):yield


def checked_parent(path, own):
    old = json.loads(private(path)); closed = Path(old['attempts_root']).resolve()
    require(own.resolve() != closed and not closed.is_relative_to(own.resolve()) and
            not own.resolve().is_relative_to(closed), 'Fresh bounded root must be separate from closed v16')
    with parent_history(own):return parent.validate(path)


def file_manifest(root):
    require(root.is_dir() and not root.is_symlink(), 'Closed evidence directory missing or unsafe')
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Closed evidence symlink changed')
        if path.is_file():result[str(path.relative_to(root))] = digest(path.read_bytes())
    return result


def closed_failure(value, reconciliation):
    root = Path(value['attempts_root'])
    receipts = list(root.glob('*/*/receipt.json')); intents = list(root.glob('*/*/intent.json'))
    require(len(receipts) == len(intents) == 1, 'Exactly one consumed v16 positive intent is required')
    out = receipts[0].parent; receipt_raw = private(receipts[0]); receipt = json.loads(receipt_raw)
    intent = json.loads(private(intents[0])); command = json.loads(private(out / 'guest-probe-command-v16.private.json'))
    observed = json.loads(command['stdout']); reference = json.loads(Path(value['guest_public']).read_bytes())
    require(receipt['source_freeze_sha256'] == value['_freeze_sha256'] == intent['source_freeze_sha256'] and
            receipt['stage'] == 'guest_content_attestation' and receipt['error_type'] == 'ReadTimeout' and
            receipt['actor_steps'] == [] and receipt['status'] == 'cleanup_unverified' and
            receipt['kill_returned'] is True and receipt.get('is_running_after_kill') is None and
            intent['attempt'] == 'positive' and intent['lease_seconds'] == 1200 and
            intent['same_intent_replay_authorized'] is False and command['exit_code'] == 0 and
            observed['identity_kind'] == parent.common.IDENTITY and
            observed['content_tree_sha256'] == reference['static_content_sha256'] and
            not (out / 'guest-content-files-v16.jsonl.gz').exists() and
            not (out / 'structural-attestation-v16.private.json').exists(),
            'Closed v16 failure, raw probe output, full lease or replay boundary changed')
    reconciled = json.loads(private(reconciliation))
    require(reconciled.get('schema') == 'cua-native-v16-terminal-provider-cleanup-reconciliation-v1' and
            reconciled.get('account_running_count') == 0 and reconciled.get('known_guest_still_active') is False and
            reconciled.get('provider_list_error_type') is None and reconciled.get('new_creates') == 0 and
            reconciled.get('model_calls') == 0 and reconciled.get('original_kill_returned') is True and
            reconciled.get('original_running_confirmation') is None and
            reconciled.get('raw_failed_receipt_sha256') == digest(receipt_raw) and
            reconciled.get('raw_status_preserved') == 'cleanup_unverified' and
            reconciled.get('same_intent_replay_authorized') is False,
            'Independent provider cleanup reconciliation changed')
    return file_manifest(root)


def prepare(*, parent_freeze, reconciliation, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)),
            'Fresh v17 paths required; consumed roots cannot receive new permits')
    old = checked_parent(parent_freeze, attempts_root); closed = closed_failure(old, reconciliation)
    # Bind the source freeze, permit, dispatch terminal evidence and external
    # provider reconciliation as raw bytes, without rewriting the failed receipt.
    stage = parent_freeze.parent
    require(reconciliation.parent.resolve() == stage.resolve(), 'Reconciliation must belong to the closed source stage')
    stage_manifest = file_manifest(stage)
    roots = list(dict.fromkeys([*[Path(p) for p in old['accounting_roots']], Path(old['attempts_root'])]))
    value = {**old, 'schema': SCHEMA, 'status': 'source_only_bounded_transfer_frozen_after_closed_v16',
        'parent_freeze_path': str(parent_freeze.resolve()), 'parent_freeze_sha256': old['_freeze_sha256'],
        'parent_source_sha256s': old['source_sha256s'], 'closed_v16_manifest': closed,
        'closed_v16_source_stage': str(stage.resolve()), 'closed_v16_source_stage_manifest': stage_manifest,
        'provider_reconciliation_path': str(reconciliation.resolve()),
        'provider_reconciliation_sha256': digest(private(reconciliation)),
        'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
        'source_sha256s': source_hashes(), 'bounded_transport_recipe': transport.RECIPE,
        'accounting_roots': [str(p.resolve()) for p in roots],
        'historical_metadata_sha256s': ORIGINAL_MANIFEST(roots, exclude=attempts_root),
        'historical_full_lease_accounting': ORIGINAL_ACCOUNTING(roots, exclude=attempts_root),
        'historical_controls_carried_into_new_epoch': 0, 'original_root_replay_authorized': False,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None); accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': value['status'],
        'private_freeze_sha256': digest(private(freeze_path)), 'source_sha256s': value['source_sha256s'],
        'parent_freeze_sha256': value['parent_freeze_sha256'],
        'provider_reconciliation_sha256': value['provider_reconciliation_sha256'],
        'structural_reference_sha256': value['structural_reference_sha256'],
        'bounded_transport_recipe': transport.RECIPE,
        'unchanged_probe_and_verifier': True, 'existing_v16_neutral_proof_retained': True,
        'new_live_neutral_transfer_proof': False, 'historical_raw_status_preserved': 'cleanup_unverified',
        'closed_v16_full_lease_intents': 1, 'closed_v16_full_lease_seconds': 1200,
        'historical_full_lease_intents': value['historical_full_lease_accounting']['past_full_lease_intents'],
        'historical_metadata_files': len(value['historical_metadata_sha256s']), 'cohort_counts': value['cohort_counts'],
        'max_actor_actions': 90, 'max_actor_wall_seconds': 720, 'lease_seconds_each': 1200,
        'maximum_new_full_lease_intents': 360, 'historical_controls_carried_into_new_epoch': 0,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False,
        'official_final_admissions': 0, 'model_calls': 0}
    accounting._write_new(public_path, public, public=True); return public


def validate(path):
    raw = private(path); value = json.loads(raw); own = Path(value['attempts_root'])
    require(value.get('schema') == SCHEMA and value.get('status') == 'source_only_bounded_transfer_frozen_after_closed_v16' and
        value.get('historical_controls_carried_into_new_epoch') == 0 and value.get('source_sha256s') == source_hashes() and
        value.get('bounded_transport_recipe') == transport.RECIPE and value.get('maximum_new_full_lease_intents') == 360 and
        value.get('lease_seconds_each') == 1200 and value.get('max_actor_actions') == 90 and
        value.get('max_actor_wall_seconds') == 720 and value.get('same_intent_replay_authorized') is False and
        value.get('original_root_replay_authorized') is False and value.get('dispatch_authorized') is False,
        'Bounded epoch source, transfer recipe or common policy changed')
    old = checked_parent(Path(value['parent_freeze_path']), own)
    reconciliation = Path(value['provider_reconciliation_path'])
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['source_sha256s'] == value['parent_source_sha256s'] and
        old['roster'] == value['roster'] and closed_failure(old, reconciliation) == value['closed_v16_manifest'] and
        digest(private(reconciliation)) == value['provider_reconciliation_sha256'] and
        file_manifest(Path(value['closed_v16_source_stage'])) == value['closed_v16_source_stage_manifest'],
        'Closed v16 source, intent, failed evidence or independent reconciliation changed')
    roots = [Path(p) for p in value['accounting_roots']]
    require(ORIGINAL_MANIFEST(roots, exclude=own) == value['historical_metadata_sha256s'] and
        ORIGINAL_ACCOUNTING(roots, exclude=own) == value['historical_full_lease_accounting'],
        'Current historical bytes or conservative full lease totals changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public['schema'] == PUBLIC_SCHEMA and public['private_freeze_sha256'] == digest(raw) and
        public['source_sha256s'] == value['source_sha256s'] and public['bounded_transport_recipe'] == transport.RECIPE and
        public['dispatch_authorized'] is False, 'Bounded public source binding changed')
    return {**value, '_freeze_sha256': digest(raw)}


def next_row(value):
    from .selection_control_bounded_worker_v17 import context
    with context():return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_bounded_worker_v17 import context
    with context():return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    with patch.object(parent, 'PERMIT_SCHEMA', PERMIT_SCHEMA):
        permit = parent.checked_permit(freeze_path, permit_path, value, row)
    require(permit.get('bounded_transport_recipe') == transport.RECIPE, 'Bounded permit transfer recipe changed')
    return permit


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path); row = next_row(value); active, count = active_hashes()
    require(row is not None and not active and count == 0, 'Bounded review requires next fresh row and provider active zero')
    accounting._write_new(permit_path, {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'],
        'source_sha256s': value['source_sha256s'], 'bounded_transport_recipe': transport.RECIPE,
        'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'split': row['split'],
        'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
        'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
    return {'status': 'one_bounded_source_trio_reviewed_no_create'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'plan', 'review'))
    parser.add_argument('--freeze', required=True, type=Path)
    for name in ('parent-freeze', 'reconciliation', 'attempts-root', 'public', 'permit'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        result = prepare(parent_freeze=args.parent_freeze, reconciliation=args.reconciliation,
                         attempts_root=args.attempts_root, freeze_path=args.freeze, public_path=args.public)
    elif args.mode == 'review':result = review(freeze_path=args.freeze, permit_path=args.permit)
    else:
        value = validate(args.freeze); row = next_row(value)
        result = {'status': 'bounded_metadata_ready_no_create', 'next_split': None if row is None else row['split']}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
