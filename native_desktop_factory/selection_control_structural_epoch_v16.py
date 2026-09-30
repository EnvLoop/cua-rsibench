"""Fresh pre-model structural-runtime epoch; old references stay immutable."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_accounting_epoch_v13 as parent
from . import v066_post_enter_epoch_v9 as core
from . import structural_guest_attestation_v16 as common
from .factory import digest
from tools.probe_desktop_projected_identity_v16 import SOURCE_FILES as PROBE_FILES

SCHEMA = 'cua-native-desktop-structural-runtime-private-v16'
PUBLIC_SCHEMA = 'cua-native-desktop-structural-runtime-public-v16'
PERMIT_SCHEMA = 'cua-native-desktop-structural-runtime-trio-permit-v16'
SOURCE_FILES = tuple(dict.fromkeys((*PROBE_FILES, 'native_desktop_factory/selection_control_structural_epoch_v16.py',
                    'native_desktop_factory/selection_control_structural_worker_v16.py')))
MAX_ACTIONS = parent.MAX_ACTIONS
ACTOR_WALL_SECONDS = parent.ACTOR_WALL_SECONDS
LEASE_SECONDS = parent.LEASE_SECONDS
accounting = parent.accounting
private = parent.private
require = parent.require
ORIGINAL_ACCOUNTING = parent.ORIGINAL_ACCOUNTING
ORIGINAL_MANIFEST = parent.metadata_manifest


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: digest((root / name).read_bytes()) for name in SOURCE_FILES}


@contextmanager
def parent_history(own):
    def roots(values):return [parent.HistoricalRoot(root, (own.resolve(),)) for root in values]
    def projected_account(values, *, exclude=None):return ORIGINAL_ACCOUNTING(roots(values), exclude=exclude)
    def projected_manifest(values, *, exclude):return ORIGINAL_MANIFEST(roots(values), exclude=exclude)
    with patch.object(parent, 'ORIGINAL_ACCOUNTING', projected_account), patch.object(parent, 'metadata_manifest', projected_manifest):yield


def checked_parent(path, own):
    old = json.loads(private(path)); closed = Path(old['attempts_root']).resolve()
    require(own.resolve() != closed and not closed.is_relative_to(own.resolve()), 'Fresh structural root cannot contain historical runs')
    with parent_history(own):return parent.validate(path)


def closed_failure(value):
    root = Path(value['attempts_root']); receipts = list(root.glob('*/*/receipt.json')); intents = list(root.glob('*/*/intent.json'))
    require(len(receipts) == len(intents) == 1, 'One exact closed v13 guest is required')
    receipt = json.loads(private(receipts[0]))
    require(receipt['source_freeze_sha256'] == value['_freeze_sha256'] and receipt['stage'] == 'guest_content_attestation' and
            receipt['error_type'] == 'ValueError' and receipt['actor_steps'] == [] and receipt['kill_returned'] is True and
            receipt['is_running_after_kill'] is False, 'Closed v13 failure or teardown changed')
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}


def neutral_proof(reference, root):
    receipt = json.loads(private(root / 'receipt.json')); command = json.loads(private(root / 'guest-probe-command-v16.private.json'))
    raw = (root / 'guest-content-files-v16.jsonl.gz').read_bytes(); observed = json.loads(command['stdout'])
    attestation = common.verify(observed, raw, json.loads(reference.read_bytes()))
    require(receipt['status'] == 'projected_runtime_identity_verified' and receipt['reference_sha256'] == digest(reference.read_bytes()) and
            receipt['kill_returned'] is True and receipt['is_running_after_kill'] is False and
            command['exit_code'] == 0 and receipt['projected_tree_sha256'] == attestation['projected_tree_sha256'] and
            receipt['raw_tree_sha256'] == attestation['raw_tree_sha256'], 'Actual neutral projected identity/cleanup missing')
    return {str(p.relative_to(root)): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}


def prepare(*, parent_freeze, reference, neutral_root, diagnostic_roots, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)), 'Fresh structural epoch paths required')
    old = checked_parent(parent_freeze, attempts_root); closed = closed_failure(old); neutral = neutral_proof(reference, neutral_root)
    roots = [Path(p) for p in old['accounting_roots']] + list(diagnostic_roots) + [neutral_root]
    value = {**old, 'schema': SCHEMA, 'status': 'pre_model_structural_runtime_frozen_after_neutral_live_proof',
             'parent_freeze_path': str(parent_freeze.resolve()), 'parent_freeze_sha256': old['_freeze_sha256'],
             'parent_source_sha256s': old['source_sha256s'], 'closed_v13_manifest': closed,
             'neutral_root': str(neutral_root.resolve()), 'neutral_manifest': neutral,
             'guest_public': str(reference.resolve()), 'structural_reference_sha256': digest(reference.read_bytes()),
             'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
             'source_sha256s': source_hashes(), 'accounting_roots': [str(p.resolve()) for p in roots],
             'historical_metadata_sha256s': ORIGINAL_MANIFEST(roots, exclude=attempts_root),
             'historical_full_lease_accounting': ORIGINAL_ACCOUNTING(roots, exclude=attempts_root),
             'historical_controls_carried_into_new_epoch': 0, 'original_root_replay_authorized': False, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None); accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': value['status'], 'private_freeze_sha256': digest(private(freeze_path)),
          'source_sha256s': value['source_sha256s'], 'structural_reference_sha256': value['structural_reference_sha256'],
          'parent_freeze_sha256': value['parent_freeze_sha256'], 'identity_kind': common.IDENTITY,
          'raw_legacy_reference_preserved': True, 'raw_tree_not_claimed_equal': True,
          'immutable_other_rows': 100660, 'only_projected_path': common.ARCHIVE,
          'exact_ssl_member_descriptor_required': True, 'all_member_payload_hashes_fixed': True,
          'mtime_only_archive_metadata_ignored': True, 'tls_configuration_changed': False,
          'historical_full_lease_intents': value['historical_full_lease_accounting']['past_full_lease_intents'],
          'historical_metadata_files': len(value['historical_metadata_sha256s']), 'cohort_counts': value['cohort_counts'],
          'max_actor_actions': 90, 'max_actor_wall_seconds': 720, 'lease_seconds_each': 1200,
          'maximum_new_full_lease_intents': 360, 'same_intent_replay_authorized': False,
          'historical_controls_carried_into_new_epoch': 0, 'dispatch_authorized': False, 'official_final_admissions': 0, 'model_calls': 0}
    accounting._write_new(public_path, public, public=True); return public


def validate(path):
    raw = private(path); value = json.loads(raw); own = Path(value['attempts_root'])
    require(value.get('schema') == SCHEMA and value.get('source_sha256s') == source_hashes() and
            value.get('maximum_new_full_lease_intents') == 360 and value.get('lease_seconds_each') == 1200 and
            value.get('max_actor_actions') == 90 and value.get('max_actor_wall_seconds') == 720 and value.get('dispatch_authorized') is False,
            'Structural epoch source or common budgets changed')
    old = checked_parent(Path(value['parent_freeze_path']), own)
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['source_sha256s'] == value['parent_source_sha256s'] and
            old['roster'] == value['roster'] and closed_failure(old) == value['closed_v13_manifest'], 'Immutable closed ancestor changed')
    reference = Path(value['guest_public'])
    require(digest(reference.read_bytes()) == value['structural_reference_sha256'] and
            neutral_proof(reference, Path(value['neutral_root'])) == value['neutral_manifest'], 'Structural reference or live neutral proof changed')
    roots = [Path(p) for p in value['accounting_roots']]
    require(ORIGINAL_MANIFEST(roots, exclude=own) == value['historical_metadata_sha256s'] and
            ORIGINAL_ACCOUNTING(roots, exclude=own) == value['historical_full_lease_accounting'], 'Current historical paths/bytes/lease totals changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public['private_freeze_sha256'] == digest(raw) and public['source_sha256s'] == value['source_sha256s'] and public['dispatch_authorized'] is False,
            'Structural public source binding changed')
    return {**value, '_freeze_sha256': digest(raw)}


def next_row(value):
    from .selection_control_structural_worker_v16 import context
    with context():return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_structural_worker_v16 import context
    with context():return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    with patch.object(parent, 'PERMIT_SCHEMA', PERMIT_SCHEMA):return parent.checked_permit(freeze_path, permit_path, value, row)


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path); row = next_row(value); active, count = active_hashes()
    require(row is not None and not active and count == 0, 'Structural review needs next fresh row and active zero')
    accounting._write_new(permit_path, {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'], 'source_sha256s': value['source_sha256s'],
             'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'split': row['split'],
             'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
             'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
    return {'status': 'one_structural_source_trio_reviewed_no_create'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('mode', choices=('prepare', 'plan', 'review'))
    p.add_argument('--freeze', required=True, type=Path)
    for name in ('parent-freeze', 'reference', 'neutral-root', 'attempts-root', 'public', 'permit'):p.add_argument('--' + name, type=Path)
    p.add_argument('--diagnostic-root', type=Path, action='append', default=[]); a = p.parse_args()
    if a.mode == 'prepare':result = prepare(parent_freeze=a.parent_freeze, reference=a.reference, neutral_root=a.neutral_root,
                 diagnostic_roots=a.diagnostic_root, attempts_root=a.attempts_root, freeze_path=a.freeze, public_path=a.public)
    elif a.mode == 'review':result = review(freeze_path=a.freeze, permit_path=a.permit)
    else:
        value = validate(a.freeze); row = next_row(value); result = {'status': 'structural_metadata_ready_no_create', 'next_split': None if row is None else row['split']}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
