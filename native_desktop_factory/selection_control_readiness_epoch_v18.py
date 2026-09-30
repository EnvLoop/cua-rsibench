"""Fresh source-only passive-readiness epoch retaining all closed v17 bytes."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_bounded_epoch_v17 as parent
from . import selection_control_accounting_epoch_v13 as history
from . import v066_post_enter_epoch_v9 as core
from . import bounded_guest_transport_v17 as transport
from . import pre_observation_readiness_v18 as readiness
from . import structural_guest_attestation_v16 as structural
from tools.audit_desktop_passive_readiness_v18 import audit as audit_closed_readiness
from .factory import digest

SCHEMA = 'cua-native-desktop-passive-readiness-private-v18'
PUBLIC_SCHEMA = 'cua-native-desktop-passive-readiness-public-v18'
PERMIT_SCHEMA = 'cua-native-desktop-passive-readiness-trio-permit-v18'
SOURCE_FILES = (*parent.SOURCE_FILES,
    'native_desktop_factory/pre_observation_readiness_v18.py',
    'native_desktop_factory/selection_control_readiness_epoch_v18.py',
    'native_desktop_factory/selection_control_readiness_worker_v18.py',
    'tools/audit_desktop_passive_readiness_v18.py',
    'tests/test_desktop_passive_readiness_v18.py')
READINESS_RECIPE = {'schema': 'cua-native-passive-readiness-policy-v18',
    'max_wall_ms': readiness.MAX_WALL_MS, 'sample_delays_ms': list(readiness.SAMPLE_DELAYS_MS),
    'required_samples': 7, 'required_settled_suffix': 4,
    'full_final_png_returned_unchanged': True, 'same_native_window_required': True,
    'exact_or_original_narrow_caret_required': True, 'action_retries': 0,
    'pixel_masking': False, 'max_actor_wall_seconds': 720}
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
    # This layer excludes only the fresh v18 descendant. v17 keeps its own
    # established exclusion while validating its closed ancestors.
    def roots(values):return [history.HistoricalRoot(root, (own.resolve(),)) for root in values]
    def projected_account(values, *, exclude=None):return ORIGINAL_ACCOUNTING(roots(values), exclude=exclude)
    def projected_manifest(values, *, exclude):return ORIGINAL_MANIFEST(roots(values), exclude=exclude)
    with patch.object(parent, 'ORIGINAL_ACCOUNTING', projected_account), \
         patch.object(parent, 'ORIGINAL_MANIFEST', projected_manifest):yield


def checked_parent(path, own):
    old = json.loads(private(path)); closed = Path(old['attempts_root']).resolve()
    require(own.resolve() != closed and not closed.is_relative_to(own.resolve()) and
            not own.resolve().is_relative_to(closed), 'Fresh bounded root must be separate from closed v17')
    with parent_history(own):return parent.validate(path)


def file_manifest(root):
    require(root.is_dir() and not root.is_symlink(), 'Closed evidence directory missing or unsafe')
    result = {}
    for path in sorted(root.rglob('*')):
        require(not path.is_symlink(), 'Closed evidence symlink changed')
        if path.is_file():result[str(path.relative_to(root))] = digest(path.read_bytes())
    return result


def closed_failure(value):
    root = Path(value['attempts_root']); receipts = list(root.glob('*/*/receipt.json'))
    require(len(receipts) == len(list(root.glob('*/*/intent.json'))) == 1, 'Exactly one consumed v17 positive is required')
    out = receipts[0].parent
    require(out == root / value['roster'][0]['task_id'] / 'positive', 'Closed v17 task identity/order changed')
    passive = audit_closed_readiness(root, out, freeze_sha256=value['_freeze_sha256'])
    command = json.loads(private(out / 'guest-probe-command-v16.private.json'))
    raw = (out / 'guest-content-files-v16.jsonl.gz').read_bytes()
    attestation = structural.verify(json.loads(command['stdout']), raw, json.loads(Path(value['guest_public']).read_bytes()))
    require(command['exit_code'] == 0 and json.loads(private(out / 'structural-attestation-v16.private.json')) == attestation,
            'Closed v17 successful manifest download and structural identity changed')
    return file_manifest(root), passive


def prepare(*, parent_freeze, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)),
            'Fresh v18 paths required; consumed roots cannot receive new permits')
    old = checked_parent(parent_freeze, attempts_root); closed, passive = closed_failure(old)
    # Retain the successful transfer, partial readiness frames, raw failure,
    # teardown, full intent and closed source stage without rewriting evidence.
    stage = parent_freeze.parent
    stage_manifest = file_manifest(stage)
    roots = list(dict.fromkeys([*[Path(p) for p in old['accounting_roots']], Path(old['attempts_root'])]))
    value = {**old, 'schema': SCHEMA, 'status': 'source_only_passive_readiness_frozen_after_closed_v17',
        'parent_freeze_path': str(parent_freeze.resolve()), 'parent_freeze_sha256': old['_freeze_sha256'],
        'parent_source_sha256s': old['source_sha256s'], 'closed_v17_manifest': closed, 'closed_v17_passive_audit': passive,
        'closed_v17_source_stage': str(stage.resolve()), 'closed_v17_source_stage_manifest': stage_manifest,
        'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
        'source_sha256s': source_hashes(), 'bounded_transport_recipe': transport.RECIPE,
        'passive_readiness_recipe': READINESS_RECIPE,
        'accounting_roots': [str(p.resolve()) for p in roots],
        'historical_metadata_sha256s': ORIGINAL_MANIFEST(roots, exclude=attempts_root),
        'historical_full_lease_accounting': ORIGINAL_ACCOUNTING(roots, exclude=attempts_root),
        'historical_controls_carried_into_new_epoch': 0, 'original_root_replay_authorized': False,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None); accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': value['status'],
        'private_freeze_sha256': digest(private(freeze_path)), 'source_sha256s': value['source_sha256s'],
        'parent_freeze_sha256': value['parent_freeze_sha256'],
        'closed_v17_passive_audit_sha256': digest(accounting.encode(passive)),
        'structural_reference_sha256': value['structural_reference_sha256'],
        'bounded_transport_recipe': transport.RECIPE, 'passive_readiness_recipe': READINESS_RECIPE,
        'unchanged_probe_and_verifier': True, 'existing_v16_neutral_proof_retained': True,
        'new_live_neutral_transfer_proof': False, 'historical_raw_status_preserved': 'control_failed_or_infrastructure_invalid',
        'closed_v17_full_lease_intents': 1, 'closed_v17_full_lease_seconds': 1200,
        'historical_full_lease_intents': value['historical_full_lease_accounting']['past_full_lease_intents'],
        'historical_metadata_files': len(value['historical_metadata_sha256s']), 'cohort_counts': value['cohort_counts'],
        'max_actor_actions': 90, 'max_actor_wall_seconds': 720, 'lease_seconds_each': 1200,
        'maximum_new_full_lease_intents': 360, 'historical_controls_carried_into_new_epoch': 0,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False,
        'official_final_admissions': 0, 'model_calls': 0}
    accounting._write_new(public_path, public, public=True); return public


def validate(path):
    raw = private(path); value = json.loads(raw); own = Path(value['attempts_root'])
    require(value.get('schema') == SCHEMA and value.get('status') == 'source_only_passive_readiness_frozen_after_closed_v17' and
        value.get('historical_controls_carried_into_new_epoch') == 0 and value.get('source_sha256s') == source_hashes() and
        value.get('bounded_transport_recipe') == transport.RECIPE and value.get('passive_readiness_recipe') == READINESS_RECIPE and
        value.get('maximum_new_full_lease_intents') == 360 and
        value.get('lease_seconds_each') == 1200 and value.get('max_actor_actions') == 90 and
        value.get('max_actor_wall_seconds') == 720 and value.get('same_intent_replay_authorized') is False and
        value.get('original_root_replay_authorized') is False and value.get('dispatch_authorized') is False,
        'Bounded epoch source, transfer recipe or common policy changed')
    old = checked_parent(Path(value['parent_freeze_path']), own)
    closed, passive = closed_failure(old)
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['source_sha256s'] == value['parent_source_sha256s'] and
        old['roster'] == value['roster'] and closed == value['closed_v17_manifest'] and
        passive == value['closed_v17_passive_audit'] and
        file_manifest(Path(value['closed_v17_source_stage'])) == value['closed_v17_source_stage_manifest'],
        'Closed v17 source, full intent, passive evidence or teardown changed')
    roots = [Path(p) for p in value['accounting_roots']]
    require(ORIGINAL_MANIFEST(roots, exclude=own) == value['historical_metadata_sha256s'] and
        ORIGINAL_ACCOUNTING(roots, exclude=own) == value['historical_full_lease_accounting'],
        'Current historical bytes or conservative full lease totals changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public['schema'] == PUBLIC_SCHEMA and public['private_freeze_sha256'] == digest(raw) and
        public['source_sha256s'] == value['source_sha256s'] and public['bounded_transport_recipe'] == transport.RECIPE and
        public['passive_readiness_recipe'] == READINESS_RECIPE and
        public['dispatch_authorized'] is False, 'Bounded public source binding changed')
    return {**value, '_freeze_sha256': digest(raw)}


def next_row(value):
    from .selection_control_readiness_worker_v18 import context
    with context():return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_readiness_worker_v18 import context
    with context():return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    with patch.object(parent, 'PERMIT_SCHEMA', PERMIT_SCHEMA):
        permit = parent.checked_permit(freeze_path, permit_path, value, row)
    require(permit.get('bounded_transport_recipe') == transport.RECIPE and
            permit.get('passive_readiness_recipe') == READINESS_RECIPE, 'Passive permit common recipes changed')
    return permit


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path); row = next_row(value); active, count = active_hashes()
    require(row is not None and not active and count == 0, 'Bounded review requires next fresh row and provider active zero')
    accounting._write_new(permit_path, {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'],
        'source_sha256s': value['source_sha256s'], 'bounded_transport_recipe': transport.RECIPE,
        'passive_readiness_recipe': READINESS_RECIPE,
        'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'split': row['split'],
        'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
        'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
    return {'status': 'one_passive_readiness_source_trio_reviewed_no_create'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'plan', 'review'))
    parser.add_argument('--freeze', required=True, type=Path)
    for name in ('parent-freeze', 'attempts-root', 'public', 'permit'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        result = prepare(parent_freeze=args.parent_freeze,
                         attempts_root=args.attempts_root, freeze_path=args.freeze, public_path=args.public)
    elif args.mode == 'review':result = review(freeze_path=args.freeze, permit_path=args.permit)
    else:
        value = validate(args.freeze); row = next_row(value)
        result = {'status': 'passive_readiness_metadata_ready_no_create', 'next_split': None if row is None else row['split']}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
