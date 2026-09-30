"""Fresh source epoch after one terminal tooltip race; no task is replaced."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from . import factory as base
from . import selection_control_successor_epoch_v10 as parent
from . import v066_post_enter_epoch_v9 as core
from tools.audit_desktop_v10b_tooltip_terminal import audit as terminal_audit

SCHEMA = 'cua-native-desktop-focus-readiness-private-v12'
PUBLIC_SCHEMA = 'cua-native-desktop-focus-readiness-public-v12'
PERMIT_SCHEMA = 'cua-native-desktop-focus-readiness-one-trio-permit-v12'
SOURCE_FILES = (*parent.SOURCE_FILES,
    'native_desktop_factory/pre_observation_readiness_v12.py',
    'native_desktop_factory/selection_control_readiness_epoch_v12.py',
    'native_desktop_factory/selection_control_readiness_worker_v12.py',
    'tools/audit_desktop_v10b_tooltip_terminal.py',
    'tests/test_desktop_focus_readiness_v12.py')
MAX_ACTIONS = parent.MAX_ACTIONS
ACTOR_WALL_SECONDS = parent.ACTOR_WALL_SECONDS
LEASE_SECONDS = parent.LEASE_SECONDS
accounting = parent.accounting
private = parent.private
require = parent.require


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: base.digest((root / name).read_bytes()) for name in SOURCE_FILES}


def prepare(*, parent_freeze, dispatch_root, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)),
            'Fresh v12 source and attempt paths are required')
    old = parent.validate(parent_freeze)
    forensic = terminal_audit(attempts_root=Path(old['attempts_root']), dispatch_root=dispatch_root)
    require(forensic['source_freeze_sha256'] == old['_freeze_sha256'], 'Terminal parent source differs')
    forensic_path = freeze_path.parent / 'tooltip-terminal.private.json'
    forensic_sha = accounting._write_new(forensic_path, forensic)
    roots = [Path(p) for p in old['accounting_roots']] + [Path(old['attempts_root'])]
    ledger = accounting.lease_accounting(roots, exclude=attempts_root)
    value = {**old, 'schema': SCHEMA, 'status': 'focus_readiness_frozen_before_any_new_create',
             'created_utc': datetime.now(timezone.utc).isoformat(),
             'parent_freeze_path': str(parent_freeze.resolve()),
             'parent_freeze_sha256': old['_freeze_sha256'],
             'parent_source_sha256s': old['source_sha256s'],
             'terminal_dispatch_root': str(dispatch_root.resolve()),
             'forensic_path': str(forensic_path.resolve()), 'forensic_sha256': forensic_sha,
             'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
             'source_sha256s': source_hashes(), 'accounting_roots': [str(p.resolve()) for p in roots],
             'historical_full_lease_accounting': ledger,
             'original_root_replay_authorized': False, 'historical_controls_carried_into_new_epoch': 0,
             'task_family_replacements_for_hover_race': 0, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None)
    accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': value['status'],
              'private_freeze_sha256': base.digest(private(freeze_path)),
              'parent_freeze_sha256': value['parent_freeze_sha256'],
              'terminal_forensic_sha256': forensic_sha, 'source_sha256s': value['source_sha256s'],
              'cohort_counts': value['cohort_counts'], 'source_family_counts': value['source_family_counts'],
              'historical_full_lease_intents': ledger['past_full_lease_intents'],
              'maximum_new_full_lease_intents': 360, 'lease_seconds_each': 1200,
              'max_actor_actions': 90, 'max_actor_wall_seconds': 720,
              'passive_focus_sample_delays_ms': [0, 250, 250, 500, 500, 500, 500],
              'passive_focus_max_wall_ms': 30000, 'exact_current_frame_parser_unchanged': True,
              'tooltip_pixels_preserved': True, 'task_family_replacements_for_hover_race': 0,
              'historical_controls_carried_into_new_epoch': 0, 'lane_spending_cap_usd': None,
              'same_intent_replay_authorized': False, 'original_root_replay_authorized': False,
              'dispatch_authorized': False, 'model_calls': 0, 'official_final_admissions': 0}
    accounting._write_new(public_path, public, public=True)
    return public


def validate(freeze_path):
    raw = private(freeze_path)
    value = json.loads(raw)
    require(value.get('schema') == SCHEMA and value.get('source_sha256s') == source_hashes() and
            value.get('maximum_new_full_lease_intents') == 360 and value.get('lease_seconds_each') == 1200 and
            value.get('max_actor_actions') == 90 and value.get('max_actor_wall_seconds') == 720 and
            value.get('dispatch_authorized') is False and value.get('same_intent_replay_authorized') is False,
            'v12 source, budgets or replay boundary changed')
    old = parent.validate(Path(value['parent_freeze_path']))
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['roster'] == value['roster'] and
            old['source_sha256s'] == value['parent_source_sha256s'] and old['attempts_root'] != value['attempts_root'],
            'v12 old source or fresh task root changed')
    forensic = terminal_audit(attempts_root=Path(old['attempts_root']), dispatch_root=Path(value['terminal_dispatch_root']))
    require(base.digest(private(Path(value['forensic_path']))) == value['forensic_sha256'] and
            forensic == json.loads(private(Path(value['forensic_path']))), 'Old terminal evidence changed')
    require(accounting.lease_accounting([Path(p) for p in value['accounting_roots']], exclude=Path(value['attempts_root'])) ==
            value['historical_full_lease_accounting'], 'v12 historical lease accounting changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public.get('schema') == PUBLIC_SCHEMA and public.get('private_freeze_sha256') == base.digest(raw) and
            public.get('source_sha256s') == value['source_sha256s'] and public.get('dispatch_authorized') is False,
            'v12 public source binding changed')
    return {**value, '_freeze_sha256': base.digest(raw)}


def next_row(value):
    from .selection_control_readiness_worker_v12 import context
    with context():
        return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_readiness_worker_v12 import context
    with context():
        return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    permit = json.loads(private(permit_path))
    require(permit.get('schema') == PERMIT_SCHEMA and permit.get('freeze_sha256') == value['_freeze_sha256'] and
            permit.get('source_sha256s') == value['source_sha256s'] and permit.get('task_id') == row['task_id'] and
            permit.get('package_sha256') == row['package_sha256'] and permit.get('split') == row['split'] and
            permit.get('attempts') == ['positive', 'near-miss', 'cold-reset'] and permit.get('maximum_new_intents') == 3 and
            permit.get('provider_active_zero_at_review') is True and permit.get('same_intent_replay_authorized') is False,
            'v12 exact fresh one-trio permit changed')
    return permit


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path)
    row = next_row(value)
    require(row is not None, 'All v12 trios are complete')
    active, count = active_hashes()
    require(not active and count == 0, 'v12 review requires independently observed provider active zero')
    permit = {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'], 'source_sha256s': value['source_sha256s'],
              'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'split': row['split'],
              'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
              'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False,
              'official_final_admissions': 0, 'official_model_results': 0}
    accounting._write_new(permit_path, permit)
    return {'status': 'v12_fresh_trio_reviewed_no_create', 'official_final_admissions': 0}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['prepare', 'plan', 'review'])
    p.add_argument('--freeze', type=Path, required=True)
    for name in ['parent-freeze', 'dispatch-root', 'attempts-root', 'public', 'permit']:
        p.add_argument('--' + name, type=Path)
    a = p.parse_args()
    if a.mode == 'prepare':
        result = prepare(parent_freeze=a.parent_freeze, dispatch_root=a.dispatch_root,
                         attempts_root=a.attempts_root, freeze_path=a.freeze, public_path=a.public)
    elif a.mode == 'review':
        result = review(freeze_path=a.freeze, permit_path=a.permit)
    else:
        value = validate(a.freeze)
        result = {'status': 'v12_metadata_ready_no_create', 'next_split': next_row(value)['split'],
                  'official_final_admissions': 0}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
