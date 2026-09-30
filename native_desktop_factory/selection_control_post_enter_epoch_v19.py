"""Fresh source-bound Enter epoch preserving the exact closed v18 failure."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch
from . import selection_control_readiness_epoch_v18 as parent
from . import selection_control_accounting_epoch_v13 as history
from . import v066_post_enter_epoch_v9 as core
from . import post_enter_component_v19 as component
from .factory import digest
from tools.audit_desktop_post_enter_v19 import audit as closed_audit

SCHEMA = 'cua-native-desktop-post-enter-private-v19'
PUBLIC_SCHEMA = 'cua-native-desktop-post-enter-public-v19'
PERMIT_SCHEMA = 'cua-native-desktop-post-enter-trio-permit-v19'
STATUS = 'source_only_post_enter_frozen_after_closed_v18'
SOURCE_FILES = (*parent.SOURCE_FILES,
    'native_desktop_factory/post_enter_component_v19.py',
    'native_desktop_factory/selection_control_post_enter_epoch_v19.py',
    'native_desktop_factory/selection_control_post_enter_worker_v19.py',
    'tools/audit_desktop_post_enter_v19.py', 'tests/test_desktop_post_enter_v19.py')
MAX_ACTIONS = parent.MAX_ACTIONS
ACTOR_WALL_SECONDS = parent.ACTOR_WALL_SECONDS
LEASE_SECONDS = parent.LEASE_SECONDS
READINESS_RECIPE = parent.READINESS_RECIPE
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
    def roots(values):return [history.HistoricalRoot(root, (own.resolve(),)) for root in values]
    with patch.object(parent, 'ORIGINAL_ACCOUNTING', lambda values, exclude=None: ORIGINAL_ACCOUNTING(roots(values), exclude=exclude)), \
         patch.object(parent, 'ORIGINAL_MANIFEST', lambda values, exclude: ORIGINAL_MANIFEST(roots(values), exclude=exclude)):yield


def checked_parent(path, own):
    closed = Path(json.loads(private(path))['attempts_root']).resolve()
    require(own.resolve() != closed and not closed.is_relative_to(own.resolve()) and not own.resolve().is_relative_to(closed),
            'Fresh v19 root must be separate from closed v18')
    with parent_history(own):return parent.validate(path)


def closed_failure(value):
    root = Path(value['attempts_root']); out = root / value['roster'][0]['task_id'] / 'positive'
    require(list(root.glob('*/*/receipt.json')) == [out / 'receipt.json'] and
            list(root.glob('*/*/intent.json')) == [out / 'intent.json'], 'One exact consumed v18 positive required')
    audit = closed_audit(root, out, freeze_sha256=value['_freeze_sha256'])
    command = json.loads(private(out / 'guest-probe-command-v16.private.json'))
    structural = parent.structural.verify(json.loads(command['stdout']), (out / 'guest-content-files-v16.jsonl.gz').read_bytes(),
                                           json.loads(Path(value['guest_public']).read_bytes()))
    require(command['exit_code'] == 0 and json.loads(private(out / 'structural-attestation-v16.private.json')) == structural,
            'Closed v18 structural identity changed')
    return parent.file_manifest(root), audit


def prepare(*, parent_freeze, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)), 'Fresh v19 authority paths required')
    old = checked_parent(parent_freeze, attempts_root); manifest, audit = closed_failure(old)
    roots = list(dict.fromkeys([*[Path(p) for p in old['accounting_roots']], Path(old['attempts_root'])]))
    value = {**old, 'schema': SCHEMA, 'status': STATUS, 'parent_freeze_path': str(parent_freeze.resolve()),
        'parent_freeze_sha256': old['_freeze_sha256'], 'parent_source_sha256s': old['source_sha256s'],
        'closed_v18_manifest': manifest, 'closed_v18_enter_audit': audit,
        'closed_v18_source_stage': str(parent_freeze.parent.resolve()),
        'closed_v18_source_stage_manifest': parent.file_manifest(parent_freeze.parent),
        'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
        'source_sha256s': source_hashes(), 'post_enter_recipe': component.RECIPE,
        'accounting_roots': [str(p.resolve()) for p in roots],
        'historical_metadata_sha256s': ORIGINAL_MANIFEST(roots, exclude=attempts_root),
        'historical_full_lease_accounting': ORIGINAL_ACCOUNTING(roots, exclude=attempts_root),
        'historical_controls_carried_into_new_epoch': 0, 'same_intent_replay_authorized': False,
        'original_root_replay_authorized': False, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None); accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': STATUS, 'private_freeze_sha256': digest(private(freeze_path)),
        'source_sha256s': value['source_sha256s'], 'parent_freeze_sha256': value['parent_freeze_sha256'],
        'post_enter_recipe': component.RECIPE, 'passive_readiness_recipe': READINESS_RECIPE,
        'closed_enter_audit_sha256': digest(accounting.encode(audit)), 'closed_v18_full_lease_seconds': 1200,
        'recorded_actor_steps': 17, 'receipt_applied_actor_steps': 16, 'raw_final_dispatch_status_preserved': 'validated_pre_dispatch',
        'historical_full_lease_intents': value['historical_full_lease_accounting']['past_full_lease_intents'],
        'cohort_counts': value['cohort_counts'], 'maximum_new_full_lease_intents': 360,
        'lease_seconds_each': 1200, 'max_actor_actions': 90, 'max_actor_wall_seconds': 720,
        'existing_v16_neutral_proof_retained': True, 'historical_controls_carried_into_new_epoch': 0,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False, 'model_calls': 0, 'official_final_admissions': 0}
    accounting._write_new(public_path, public, public=True); return public


def validate(path):
    raw = private(path); value = json.loads(raw); own = Path(value['attempts_root'])
    require(value.get('schema') == SCHEMA and value.get('status') == STATUS and value.get('source_sha256s') == source_hashes() and
        value.get('post_enter_recipe') == component.RECIPE and value.get('passive_readiness_recipe') == READINESS_RECIPE and
        value.get('maximum_new_full_lease_intents') == 360 and value.get('lease_seconds_each') == 1200 and
        value.get('max_actor_actions') == 90 and value.get('max_actor_wall_seconds') == 720 and
        value.get('historical_controls_carried_into_new_epoch') == 0 and value.get('same_intent_replay_authorized') is False and
        value.get('original_root_replay_authorized') is False and value.get('dispatch_authorized') is False, 'V19 common source, policy or authority changed')
    old = checked_parent(Path(value['parent_freeze_path']), own); manifest, audit = closed_failure(old)
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['source_sha256s'] == value['parent_source_sha256s'] and
        old['roster'] == value['roster'] and manifest == value['closed_v18_manifest'] and audit == value['closed_v18_enter_audit'] and
        parent.file_manifest(Path(value['closed_v18_source_stage'])) == value['closed_v18_source_stage_manifest'], 'Closed v18 evidence or source stage changed')
    roots = [Path(p) for p in value['accounting_roots']]
    require(ORIGINAL_MANIFEST(roots, exclude=own) == value['historical_metadata_sha256s'] and
        ORIGINAL_ACCOUNTING(roots, exclude=own) == value['historical_full_lease_accounting'], 'V19 historical bytes or full leases changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public['schema'] == PUBLIC_SCHEMA and public['private_freeze_sha256'] == digest(raw) and
        public['source_sha256s'] == value['source_sha256s'] and public['post_enter_recipe'] == component.RECIPE and
        public['dispatch_authorized'] is False, 'V19 public source binding changed')
    return {**value, '_freeze_sha256': digest(raw)}


def next_row(value):
    from .selection_control_post_enter_worker_v19 import context
    with context():return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_post_enter_worker_v19 import context
    with context():return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    with patch.object(parent, 'PERMIT_SCHEMA', PERMIT_SCHEMA):permit = parent.checked_permit(freeze_path, permit_path, value, row)
    require(permit.get('post_enter_recipe') == component.RECIPE, 'V19 permit component policy changed'); return permit


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path); row = next_row(value); active, count = active_hashes()
    require(row is not None and not active and count == 0, 'V19 review requires next fresh row and provider active zero')
    accounting._write_new(permit_path, {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'],
        'source_sha256s': value['source_sha256s'], 'bounded_transport_recipe': value['bounded_transport_recipe'],
        'passive_readiness_recipe': READINESS_RECIPE, 'post_enter_recipe': component.RECIPE,
        **{k: row[k] for k in ('task_id', 'package_sha256', 'split')}, 'attempts': ['positive', 'near-miss', 'cold-reset'],
        'maximum_new_intents': 3, 'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False})
    return {'status': 'one_enter_source_trio_reviewed_no_create'}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('mode', choices=('prepare', 'plan', 'review'))
    parser.add_argument('--freeze', type=Path, required=True)
    for name in ('parent-freeze', 'attempts-root', 'public', 'permit'):parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':result = prepare(parent_freeze=args.parent_freeze, attempts_root=args.attempts_root,
                                               freeze_path=args.freeze, public_path=args.public)
    elif args.mode == 'review':result = review(freeze_path=args.freeze, permit_path=args.permit)
    else:
        value = validate(args.freeze); row = next_row(value); result = {'status': 'enter_metadata_ready_no_create', 'next_split': None if row is None else row['split']}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
