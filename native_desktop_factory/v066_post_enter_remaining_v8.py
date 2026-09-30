"""Remaining-only, one-use TRAIN continuation after immutable v7 stop.

Exactly three fresh leases: prior modal source reset, unused no-action source
probe, and its reset. No modal replay, wrong-target replay or final entry exists.
The old title classifier and terminal status remain unchanged.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path

from . import v066_post_enter_near_negative_v7 as old
from .reconcile_interrupted_sweep import active_hashes
from .v066_post_enter_train_calibration_v1 import SDK_VERSIONS
from .v066_storage_budget import audit as storage_audit


SCHEMA = 'cua-native-wdi-v066-post-enter-remaining-freeze-private-v8'
PUBLIC_SCHEMA = 'cua-native-wdi-v066-post-enter-remaining-freeze-public-v8'
RUN_SCHEMA = 'cua-native-wdi-v066-post-enter-remaining-run-private-v8'
MAX_GUESTS = 3
SEQUENCE = (('modal-stop', 'cold-reset'), ('no-action-probe', 'case'), ('no-action-probe', 'cold-reset'))
OLD_RUN_SHA256 = '84673c00d2ac7b9d2d7e7542b98c9b1821ff8c56a4cd1f36b00bef7a1d4910a6'
OLD_FREEZE_SHA256 = '3d07de0393b4a7239f088be633f71e0959380bd67ed1992d77c4c9b6cc1772c0'
OLD_PERMIT_SHA256 = '0b75f9a5f7d052100bac2d5c4717d2d301265ec690362e593bd8f8ebacb7ca0f'
SOURCE_FILES = (*old.SOURCE_FILES,
    'native_desktop_factory/v066_post_enter_remaining_v8.py',
    'native_desktop_factory/v066_post_enter_remaining_audit_v8.py',
    'tests/test_native_desktop_post_enter_remaining_v8.py')


def source_hashes() -> dict:
    repo = Path(__file__).resolve().parents[1]
    return {name: old.digest((repo/name).read_bytes()) for name in SOURCE_FILES}


def old_bindings(*, old_freeze: Path, old_run: Path) -> tuple[dict, dict]:
    if (old.digest(old._private(old_freeze)) != OLD_FREEZE_SHA256 or
            old.digest(old._private(old_run)) != OLD_RUN_SHA256):
        raise ValueError('Immutable old v7 freeze/run bytes changed')
    value = old.validate_source(old_freeze, require_unused=False)
    run = json.loads(old._private(old_run))
    permit_path = Path(run.get('permit_path', ''))
    if (not permit_path.is_absolute() or old.digest(old._private(permit_path)) != OLD_PERMIT_SHA256 or
            run.get('schema') != old.RUN_SCHEMA or run.get('status') != 'stopped_for_reconciliation' or
            run.get('freeze_sha256') != OLD_FREEZE_SHA256 or run.get('permit_sha256') != OLD_PERMIT_SHA256 or
            run.get('official_final_admissions') != 0 or len(run.get('attempts', [])) != 3):
        raise ValueError('Old three-intent terminal stop or exact permit changed')
    return value, run


def _sequence(value: dict) -> list[dict]:
    sources = {source['case']: source for source in value['cases']}
    return [{'source': sources[case], 'attempt': attempt} for case, attempt in SEQUENCE]


def prepare(*, old_freeze: Path, old_run: Path, terminal_audit: Path,
            visual_adjudication: Path, output_root: Path, freeze_path: Path,
            public_path: Path) -> dict:
    from .v066_post_enter_remaining_audit_v8 import validate_terminal_records
    value, run = old_bindings(old_freeze=old_freeze, old_run=old_run)
    evidence = validate_terminal_records(old_freeze=old_freeze, old_run=old_run,
        terminal_audit=terminal_audit, visual_adjudication=visual_adjudication)
    paths = [old_freeze, old_run, terminal_audit, visual_adjudication, output_root, freeze_path, public_path]
    if (not all(path.is_absolute() for path in paths) or
            any(path.exists() or path.is_symlink() for path in [output_root, freeze_path, public_path]) or
            output_root.parent.resolve() != (Path(value['work_root'])/'gui-diagnostics').resolve() or
            output_root == Path(value['output_root'])):
        raise ValueError('New exclusive remaining-only TRAIN epoch paths required')
    ledger = old.lease_accounting([Path(path) for path in value['accounting_roots']])
    chosen = _sequence(value)
    modal_package = chosen[0]['source']['row']['package_sha256']
    probe_package = chosen[1]['source']['row']['package_sha256']
    if modal_package not in ledger['used_package_sha256s'] or probe_package in ledger['used_package_sha256s']:
        raise ValueError('Continuation must reset used modal source and probe only unused TRAIN source')
    frozen = {'schema': SCHEMA, 'status': 'source_frozen_no_dispatch', 'created_utc': old._now(),
        'old_freeze_path': str(old_freeze), 'old_freeze_sha256': OLD_FREEZE_SHA256,
        'old_run_path': str(old_run), 'old_run_sha256': OLD_RUN_SHA256,
        'old_permit_path': run['permit_path'], 'old_permit_sha256': OLD_PERMIT_SHA256,
        'terminal_audit_path': str(terminal_audit), 'terminal_audit_sha256': old.digest(old._private(terminal_audit)),
        'visual_adjudication_path': str(visual_adjudication), 'visual_adjudication_sha256': old.digest(old._private(visual_adjudication)),
        'prior_receipt_sha256s': [row['receipt_sha256'] for row in run['attempts']],
        'source_sha256s': source_hashes(), 'work_root': value['work_root'], 'candidate_root': value['candidate_root'],
        'accounting_roots': value['accounting_roots'], 'guest_public': value['guest_public'],
        'guest_public_sha256': value['guest_public_sha256'], 'scoped_reference': value['scoped_reference'],
        'scoped_reference_sha256': value['scoped_reference_sha256'], 'output_root': str(output_root),
        'public_path': str(public_path), 'sequence': chosen, 'prior_full_lease_accounting': ledger,
        'maximum_new_full_lease_intents': MAX_GUESTS, 'lease_seconds_each': old.LEASE_SECONDS,
        'new_full_lease_seconds': MAX_GUESTS*old.LEASE_SECONDS, 'new_full_lease_usd_planning_upper': '0.5',
        'lane_spending_cap_usd': None, 'same_intent_replay_authorized': False, 'dispatch_authorized': False,
        'original_v7_terminal_status': evidence['original_v7_terminal_status'],
        'official_final_admissions': 0, 'official_model_results': 0}
    freeze_sha = old._write_new(freeze_path, frozen)
    public = {'schema': PUBLIC_SCHEMA, 'status': 'remaining_train_only_frozen_pending_root_review',
        'private_freeze_sha256': freeze_sha, 'source_sha256s': frozen['source_sha256s'],
        'old_freeze_sha256': OLD_FREEZE_SHA256, 'old_run_sha256': OLD_RUN_SHA256,
        'old_permit_sha256': OLD_PERMIT_SHA256, 'terminal_audit_sha256': frozen['terminal_audit_sha256'],
        'visual_adjudication_sha256': frozen['visual_adjudication_sha256'],
        'old_paid_intents_preserved': 3, 'old_modal_case_replay_authorized': False,
        'remaining_original_byte_resets': 2, 'unused_train_no_action_probe': 1,
        'maximum_new_full_lease_intents': MAX_GUESTS, 'lease_seconds_each': old.LEASE_SECONDS,
        'new_full_lease_seconds': MAX_GUESTS*old.LEASE_SECONDS, 'full_lease_usd_planning_upper': '0.5',
        'lane_spending_cap_usd': None, 'past_full_lease_intents': ledger['past_full_lease_intents'],
        'past_full_lease_seconds': ledger['past_full_lease_seconds'],
        'private_lease_metadata_ledger_sha256': ledger['metadata_ledger_sha256'],
        'heldout_selection_final_packages_read': 0, 'no_observed_material_oscillation_is_inconclusive': True,
        'same_intent_replay_authorized': False, 'dispatch_authorized': False,
        'official_final_admissions': 0, 'official_model_results': 0}
    old._write_new(public_path, public, public=True)
    return public


def validate_source(freeze_path: Path, *, require_unused: bool = True) -> dict:
    from .v066_post_enter_remaining_audit_v8 import validate_terminal_records
    raw = old._private(freeze_path); frozen = json.loads(raw)
    if (frozen.get('schema') != SCHEMA or frozen.get('status') != 'source_frozen_no_dispatch' or
            frozen.get('source_sha256s') != source_hashes() or frozen.get('maximum_new_full_lease_intents') != MAX_GUESTS or
            frozen.get('old_freeze_sha256') != OLD_FREEZE_SHA256 or frozen.get('old_run_sha256') != OLD_RUN_SHA256 or
            frozen.get('old_permit_sha256') != OLD_PERMIT_SHA256 or
            frozen.get('lease_seconds_each') != old.LEASE_SECONDS or frozen.get('new_full_lease_seconds') != 1800 or
            frozen.get('new_full_lease_usd_planning_upper') != '0.5' or
            frozen.get('lane_spending_cap_usd') is not None or frozen.get('same_intent_replay_authorized') is not False or
            frozen.get('dispatch_authorized') is not False or frozen.get('official_final_admissions') != 0 or
            frozen.get('official_model_results') != 0):
        raise ValueError('Remaining-only TRAIN source/three-lease protocol changed')
    value, run = old_bindings(old_freeze=Path(frozen['old_freeze_path']), old_run=Path(frozen['old_run_path']))
    if (frozen.get('sequence') != _sequence(value) or frozen.get('prior_receipt_sha256s') != [r['receipt_sha256'] for r in run['attempts']] or
            frozen.get('old_permit_path') != run['permit_path']):
        raise ValueError('Remaining sequence or immutable prior receipt binding changed')
    for field in ['work_root', 'candidate_root', 'accounting_roots', 'guest_public', 'guest_public_sha256',
                  'scoped_reference', 'scoped_reference_sha256']:
        if frozen[field] != value[field]: raise ValueError('Continuation TRAIN/runtime source binding changed')
    terminal = Path(frozen['terminal_audit_path']); visual = Path(frozen['visual_adjudication_path'])
    if old.digest(old._private(terminal)) != frozen['terminal_audit_sha256'] or old.digest(old._private(visual)) != frozen['visual_adjudication_sha256']:
        raise ValueError('Immutable terminal/visual adjudication bytes changed')
    validate_terminal_records(old_freeze=Path(frozen['old_freeze_path']), old_run=Path(frozen['old_run_path']),
        terminal_audit=terminal, visual_adjudication=visual)
    public = json.loads(Path(frozen['public_path']).read_bytes())
    if (public.get('schema') != PUBLIC_SCHEMA or public.get('private_freeze_sha256') != old.digest(raw) or
            public.get('source_sha256s') != frozen['source_sha256s'] or public.get('dispatch_authorized') is not False or
            public.get('maximum_new_full_lease_intents') != MAX_GUESTS):
        raise ValueError('Public remaining-only source receipt changed')
    if require_unused:
        ledger = old.lease_accounting([Path(p) for p in frozen['accounting_roots']], exclude=Path(frozen['output_root']))
        if (ledger != frozen['prior_full_lease_accounting'] or
                frozen['sequence'][1]['source']['row']['package_sha256'] in ledger['used_package_sha256s']):
            raise ValueError('Prior full-lease metadata or unused probe source changed')
    return frozen


def run(*, freeze_path: Path, permit_path: Path, enable_paid_remaining_train: bool = False) -> dict:
    if enable_paid_remaining_train is not True: raise ValueError('Paid remaining-only TRAIN entry is disabled')
    from .v066_post_enter_remaining_audit_v8 import checked_permit, audit
    value = validate_source(freeze_path)
    checked_permit(freeze_path=freeze_path, permit_path=permit_path, value=value)
    root = Path(value['output_root'])
    if root.exists() or root.is_symlink(): raise ValueError('Consumed remaining-only TRAIN epoch cannot be replayed')
    if {k: importlib.metadata.version(k) for k in SDK_VERSIONS} != SDK_VERSIONS or not os.environ.get('E2B_API_KEY'):
        raise ValueError('Pinned SDK/private credential unavailable')
    active, count = active_hashes()
    if active or count: raise ValueError('Provider must be active-zero before new epoch consumption')
    if storage_audit(root.parent)['dispatch_storage_ready'] is not True:
        raise ValueError('Remaining-only raw storage unavailable')
    root.mkdir(mode=0o700)
    journal = {'schema': RUN_SCHEMA, 'status': 'started', 'created_utc': old._now(),
        'freeze_sha256': old.digest(old._private(freeze_path)), 'permit_sha256': old.digest(old._private(permit_path)),
        'permit_path': str(permit_path), 'old_run_sha256': OLD_RUN_SHA256, 'source_sha256s': value['source_sha256s'],
        'guest_count_maximum': MAX_GUESTS, 'attempts': [], 'same_intent_replay_authorized': False,
        'official_final_admissions': 0, 'official_model_results': 0}
    old._write_new(root/'run-receipt.json', journal)
    try:
        from e2b_desktop import Sandbox
        for ordinal, planned in enumerate(value['sequence']):
            receipt = old._one(value=value, source=planned['source'], attempt=planned['attempt'], ordinal=ordinal,
                freeze_sha=journal['freeze_sha256'], permit_sha=journal['permit_sha256'], sandbox_factory=Sandbox.create)
            name = f'{ordinal:02d}-{planned["source"]["case"]}-{planned["attempt"]}'
            journal['attempts'].append({'ordinal': ordinal, 'case': planned['source']['case'], 'attempt': planned['attempt'],
                'status': receipt['status'], 'receipt_sha256': old.digest(old._private(root/name/'receipt.json'))})
            old._persist(root/'run-receipt.json', journal)
            expected = 'cold_reset_observed' if planned['attempt'] == 'cold-reset' else 'no_action_probe_audited'
            if receipt['status'] != expected: raise ValueError('Remaining-only intent failed; no subsequent create or replay')
        result = audit(freeze_path=freeze_path, run_path=root/'run-receipt.json')
        journal['status'] = result['status']; journal['audit'] = result
    except Exception as exc:
        journal['status'] = 'stopped_for_reconciliation'; journal['error_type'] = type(exc).__name__
    journal['finished_utc'] = old._now(); old._persist(root/'run-receipt.json', journal)
    return {'status': journal['status'], 'run_sha256': old.digest(old._private(root/'run-receipt.json')),
        'new_full_lease_intents': len(list(root.glob('*/intent.json'))), 'official_final_admissions': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'validate', 'run']); parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--old-freeze', type=Path); parser.add_argument('--old-run', type=Path)
    parser.add_argument('--terminal-audit', type=Path); parser.add_argument('--visual-adjudication', type=Path)
    parser.add_argument('--output-root', type=Path); parser.add_argument('--public-out', type=Path)
    parser.add_argument('--permit', type=Path); parser.add_argument('--enable-paid-remaining-train', action='store_true')
    args = parser.parse_args()
    if args.mode == 'prepare':
        if not all([args.old_freeze,args.old_run,args.terminal_audit,args.visual_adjudication,args.output_root,args.public_out]):
            raise ValueError('Exact remaining-only TRAIN source preparation paths required')
        result = prepare(old_freeze=args.old_freeze, old_run=args.old_run, terminal_audit=args.terminal_audit,
            visual_adjudication=args.visual_adjudication, output_root=args.output_root, freeze_path=args.freeze, public_path=args.public_out)
    elif args.mode == 'validate':
        validate_source(args.freeze); result = {'status': 'remaining_train_source_frozen_no_dispatch',
            'private_freeze_sha256': old.digest(old._private(args.freeze)), 'maximum_new_full_lease_intents': MAX_GUESTS}
    else:
        if args.permit is None: raise ValueError('Exact root-reviewed remaining-only TRAIN permit required')
        result = run(freeze_path=args.freeze, permit_path=args.permit, enable_paid_remaining_train=args.enable_paid_remaining_train)
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__': main()
