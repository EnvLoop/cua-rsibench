"""Bound ancestor accounting to history, preserving every raw metadata byte."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_readiness_epoch_v12 as parent
from . import v066_post_enter_epoch_v9 as core
from .factory import digest

SCHEMA = 'cua-native-desktop-ancestor-accounting-private-v13'
PUBLIC_SCHEMA = 'cua-native-desktop-ancestor-accounting-public-v13'
PERMIT_SCHEMA = 'cua-native-desktop-ancestor-accounting-one-trio-permit-v13'
SOURCE_FILES = (*parent.SOURCE_FILES,
    'native_desktop_factory/selection_control_accounting_epoch_v13.py',
    'native_desktop_factory/selection_control_accounting_worker_v13.py',
    'tests/test_desktop_ancestor_accounting_v13.py')
MAX_ACTIONS = parent.MAX_ACTIONS
ACTOR_WALL_SECONDS = parent.ACTOR_WALL_SECONDS
LEASE_SECONDS = parent.LEASE_SECONDS
accounting = parent.accounting
private = parent.private
require = parent.require
ORIGINAL_ACCOUNTING = accounting.lease_accounting
PATTERNS = ('intent.json', 'receipt.json', 'batch-receipt.json', 'health-probe*.json')


class HistoricalRoot:
    """Read the real paths; omit only explicitly frozen descendant run roots."""
    def __init__(self, root, excludes):self.root = root; self.excludes = excludes
    def rglob(self, pattern):
        require(pattern in PATTERNS, 'Unexpected ancestor accounting metadata pattern')
        for path in self.root.rglob(pattern):
            if not any(path.resolve().is_relative_to(root) for root in self.excludes):
                yield path


@contextmanager
def ancestor_history(excludes):
    excludes = tuple(Path(p).resolve() for p in excludes)
    def projected(roots, *, exclude=None):
        return ORIGINAL_ACCOUNTING([HistoricalRoot(root, excludes) for root in roots], exclude=exclude)
    with patch.object(accounting, 'lease_accounting', projected):
        yield


def metadata_manifest(roots, *, exclude):
    result = {}
    for root in roots:
        for pattern in PATTERNS:
            for path in root.rglob(pattern):
                require(not path.is_symlink(), 'Historical metadata symlink changed')
                if not path.resolve().is_relative_to(exclude.resolve()):
                    result[str(path.resolve())] = digest(path.read_bytes())
    return dict(sorted(result.items()))


def terminal_forensic(parent_freeze, dispatch_root):
    value = json.loads(private(parent_freeze)); root = Path(value['attempts_root'])
    files = sorted(p for p in root.rglob('*') if p.is_file())
    expected = [root / value['roster'][0]['task_id'] / 'positive/intent.json',
                root / value['roster'][0]['task_id'] / 'trio-started.json']
    require(files == sorted(expected), 'Expected exact two-file pre-create accounting stop')
    intent = json.loads(private(expected[0])); started = json.loads(private(expected[1]))
    terminal = json.loads(private(dispatch_root / 'worker-terminal.private.json'))
    stderr = private(dispatch_root / 'worker.stderr.private.log')
    require(intent['source_freeze_sha256'] == started['source_freeze_sha256'] == digest(private(parent_freeze)) and
            intent['attempt'] == 'positive' and intent['lease_seconds'] == 1200 and
            terminal['exit_code'] == 1 and terminal['automatic_restarts'] == 0 and
            digest(stderr) == terminal['stderr_sha256'] and
            b'v10_historical_intents_or_lease_metadata_changed' in stderr,
            'Pre-create accounting traceback, source or lease changed')
    return {'schema': 'cua-native-v12-precreate-accounting-terminal-forensic',
            'status': 'ancestor_accounting_failed_before_child_marker_and_provider_create',
            'parent_freeze_sha256': digest(private(parent_freeze)),
            'attempt_metadata_sha256s': {str(p.relative_to(root)): digest(private(p)) for p in files},
            'dispatch_metadata_sha256s': {str(p.relative_to(dispatch_root)): digest(private(p))
                                        for p in sorted(dispatch_root.rglob('*')) if p.is_file()},
            'consumed_intents': 1, 'conservative_full_lease_seconds': 1200,
            'provider_create_not_reached_by_frozen_traceback': True, 'actual_provider_creates': 0,
            'same_intent_replay_authorized': False, 'official_final_admissions': 0, 'model_calls': 0}


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    return {name: digest((root / name).read_bytes()) for name in SOURCE_FILES}


def checked_parent(parent_freeze, fresh_root):
    prior = json.loads(private(parent_freeze))
    closed_root = Path(prior['attempts_root']).resolve()
    require(fresh_root.resolve() != closed_root and not closed_root.is_relative_to(fresh_root.resolve()),
            'Fresh projection root must not contain historical runs')
    with ancestor_history((closed_root, fresh_root)):
        return parent.validate(parent_freeze)


def prepare(*, parent_freeze, dispatch_root, attempts_root, freeze_path, public_path):
    require(not any(p.exists() or p.is_symlink() for p in (attempts_root, freeze_path, public_path)), 'Fresh v13 paths required')
    old = checked_parent(parent_freeze, attempts_root)
    forensic = terminal_forensic(parent_freeze, dispatch_root)
    forensic_path = freeze_path.parent / 'precreate-accounting-terminal.private.json'
    forensic_sha = accounting._write_new(forensic_path, forensic)
    roots = [Path(p) for p in old['accounting_roots']]
    manifest = metadata_manifest(roots, exclude=attempts_root)
    ledger = ORIGINAL_ACCOUNTING(roots, exclude=attempts_root)
    value = {**old, 'schema': SCHEMA, 'status': 'ancestor_history_frozen_before_new_create',
             'parent_freeze_path': str(parent_freeze.resolve()), 'parent_freeze_sha256': old['_freeze_sha256'],
             'parent_source_sha256s': old['source_sha256s'], 'terminal_dispatch_root': str(dispatch_root.resolve()),
             'forensic_path': str(forensic_path.resolve()), 'forensic_sha256': forensic_sha,
             'attempts_root': str(attempts_root.resolve()), 'public_path': str(public_path.resolve()),
             'historical_metadata_sha256s': manifest, 'historical_full_lease_accounting': ledger,
             'source_sha256s': source_hashes(), 'original_root_replay_authorized': False,
             'historical_controls_carried_into_new_epoch': 0, 'dispatch_authorized': False}
    value.pop('_freeze_sha256', None)
    accounting._write_new(freeze_path, value)
    public = {'schema': PUBLIC_SCHEMA, 'status': value['status'], 'private_freeze_sha256': digest(private(freeze_path)),
              'source_sha256s': value['source_sha256s'], 'parent_freeze_sha256': value['parent_freeze_sha256'],
              'terminal_forensic_sha256': forensic_sha, 'cohort_counts': value['cohort_counts'],
              'historical_metadata_files': len(manifest), 'historical_metadata_manifest_sha256': digest(accounting.encode(manifest)),
              'historical_full_lease_intents': ledger['past_full_lease_intents'],
              'retained_precreate_intents': 1, 'retained_precreate_actual_provider_creates': 0,
              'maximum_new_full_lease_intents': 360, 'lease_seconds_each': 1200,
              'max_actor_actions': 90, 'max_actor_wall_seconds': 720,
              'passive_focus_readiness_v12_unchanged': True, 'frozen_v12_source_files_unchanged': 65,
              'historical_controls_carried_into_new_epoch': 0, 'same_intent_replay_authorized': False,
              'dispatch_authorized': False, 'model_calls': 0, 'official_final_admissions': 0}
    accounting._write_new(public_path, public, public=True)
    return public


def validate(freeze_path):
    raw = private(freeze_path); value = json.loads(raw); own = Path(value['attempts_root'])
    require(value.get('schema') == SCHEMA and value.get('source_sha256s') == source_hashes() and
            value.get('maximum_new_full_lease_intents') == 360 and value.get('lease_seconds_each') == 1200 and
            value.get('max_actor_actions') == 90 and value.get('max_actor_wall_seconds') == 720 and
            value.get('dispatch_authorized') is False and value.get('same_intent_replay_authorized') is False,
            'v13 source, budget or replay boundary changed')
    old = checked_parent(Path(value['parent_freeze_path']), own)
    require(old['_freeze_sha256'] == value['parent_freeze_sha256'] and old['source_sha256s'] == value['parent_source_sha256s'] and
            old['roster'] == value['roster'], 'Frozen ancestor source or roster changed')
    forensic = terminal_forensic(Path(value['parent_freeze_path']), Path(value['terminal_dispatch_root']))
    require(digest(private(Path(value['forensic_path']))) == value['forensic_sha256'] and
            json.loads(private(Path(value['forensic_path']))) == forensic, 'Closed pre-create root changed')
    roots = [Path(p) for p in value['accounting_roots']]
    require(metadata_manifest(roots, exclude=own) == value['historical_metadata_sha256s'] and
            ORIGINAL_ACCOUNTING(roots, exclude=own) == value['historical_full_lease_accounting'],
            'Historical metadata bytes, paths or conservative lease totals changed')
    public = json.loads(Path(value['public_path']).read_bytes())
    require(public.get('schema') == PUBLIC_SCHEMA and public.get('private_freeze_sha256') == digest(raw) and
            public.get('source_sha256s') == value['source_sha256s'] and public.get('dispatch_authorized') is False,
            'v13 public source binding changed')
    return {**value, '_freeze_sha256': digest(raw)}


def next_row(value):
    from .selection_control_accounting_worker_v13 import context
    with context():return core.next_row(value)


def checked_inflight(value, row, attempt):
    from .selection_control_accounting_worker_v13 import context
    with context():return core.checked_inflight(value, row, attempt)


def checked_permit(freeze_path, permit_path, value, row):
    with patch.object(parent, 'PERMIT_SCHEMA', PERMIT_SCHEMA):
        return parent.checked_permit(freeze_path, permit_path, value, row)


def review(*, freeze_path, permit_path):
    from .reconcile_interrupted_sweep import active_hashes
    value = validate(freeze_path); row = next_row(value)
    require(row is not None, 'All v13 trios completed')
    active, count = active_hashes(); require(not active and count == 0, 'Review requires provider active zero')
    permit = {'schema': PERMIT_SCHEMA, 'freeze_sha256': value['_freeze_sha256'], 'source_sha256s': value['source_sha256s'],
              'task_id': row['task_id'], 'package_sha256': row['package_sha256'], 'split': row['split'],
              'attempts': ['positive', 'near-miss', 'cold-reset'], 'maximum_new_intents': 3,
              'provider_active_zero_at_review': True, 'same_intent_replay_authorized': False,
              'official_final_admissions': 0, 'official_model_results': 0}
    accounting._write_new(permit_path, permit)
    return {'status': 'v13_fresh_one_trio_reviewed_no_create'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('mode', choices=('prepare', 'plan', 'review'))
    p.add_argument('--freeze', required=True, type=Path)
    for name in ('parent-freeze', 'dispatch-root', 'attempts-root', 'public', 'permit'):p.add_argument('--' + name, type=Path)
    a = p.parse_args()
    if a.mode == 'prepare':result = prepare(parent_freeze=a.parent_freeze, dispatch_root=a.dispatch_root,
                    attempts_root=a.attempts_root, freeze_path=a.freeze, public_path=a.public)
    elif a.mode == 'review':result = review(freeze_path=a.freeze, permit_path=a.permit)
    else:
        value = validate(a.freeze); row = next_row(value)
        result = {'status': 'v13_metadata_ready_no_create', 'next_split': None if row is None else row['split']}
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':main()
