"""Independent exact TRAIN permit and saved/raw evidence auditor for v7.

Permit issuance never creates a provider guest. Raw real-provider evidence is
required for real-modal/oscillation claims; a stable or caret-only probe stays
inconclusive. Nothing here can admit or resume an official final task.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, datetime
import json
import math
from pathlib import Path

from cursibench.scale_action_output_v066 import normalize_model_action
from . import admit, qwen_v066_adapter as adapter, v066_profile_scope_analysis as scope
from .qwen_v064_adapter import application_frame_digest
from .reconcile_interrupted_sweep import active_hashes
from .v066_scoped_profile_reference import validate_reference
from .v066_storage_budget import audit as storage_audit
from .verify import formula_key, verify, xlsx_cells, _same_value
from .v066_post_enter_near_negative_v7 import (
    INTENT_SCHEMA, RECEIPT_SCHEMA, RUN_SCHEMA, LEASE_SECONDS, MAX_GUESTS,
    SAMPLE_DELAYS_MS, MAX_PROBE_WALL_MS, TRUSTED_STIMULI, _private,
    _write_new, actions_for, digest, encode, lease_accounting, validate_source,
)


REVIEW_SCHEMA = 'cua-native-wdi-v066-post-enter-near-negative-review-private-v7'
PERMIT_SCHEMA = 'cua-native-wdi-v066-post-enter-near-negative-permit-private-v7'


def bound(root: Path, reference: dict) -> bytes:
    name = reference.get('private_path')
    if type(name) is not str or Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('Unsafe private raw-evidence reference')
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Private evidence escaped run root')
    raw = _private(path)
    if digest(raw) != reference.get('sha256') or len(raw) != reference.get('bytes'):
        raise ValueError('Retained raw evidence bytes changed')
    return raw


def wrong_target_score(baseline: bytes, saved: bytes, oracle: dict) -> dict:
    """Require correct formula/result in B5, untouched B4, and score zero.

    Source OOXML changes to any other cell invalidate this control. The normal
    task verifier is reopened independently; screenshots never supply score.
    """
    if (oracle.get('split') != 'train' or list(oracle.get('targets', {})) != ['Review!B4'] or saved == baseline):
        raise ValueError('Wrong-target control requires changed TRAIN saved bytes')
    before, after = xlsx_cells(baseline), xlsx_cells(saved)
    if set(before) != set(after) or any(set(before[s]) != set(after[s]) for s in before):
        raise ValueError('Wrong-target control changed worksheet/cell inventory')
    changed = []
    for sheet, cells in before.items():
        for address, old in cells.items():
            new = after[sheet][address]
            same_formula = formula_key(old['formula']) == formula_key(new['formula'])
            same_value = (old['formula'] is not None and old['value'] is None) or _same_value(old['value'], new['value'])
            if not same_formula or not same_value:
                changed.append(f'{sheet}!{address}')
    if changed != ['Review!B5']:
        raise ValueError('Saved GUI control must change exactly wrong target B5')
    intended = oracle['targets']['Review!B4']
    wrong = after['Review']['B5']
    try: cached = float(wrong['value'])
    except (TypeError, ValueError): raise ValueError('Wrong-target formula cached result absent') from None
    if (formula_key(wrong['formula']) != formula_key(intended['formula']) or
            not math.isfinite(cached) or not math.isclose(cached, intended['expected_value'], rel_tol=2e-10, abs_tol=1e-6)):
        raise ValueError('Wrong-target edit is not the intended formula/result')
    verdict = verify(baseline, saved, oracle)
    errors = verdict.get('errors', [])
    if (verdict.get('passed') is not False or 'non_target_changed:Review!B5' not in errors or
            not any(x.startswith('target_') and x.endswith('Review!B4') for x in errors) or
            any(not (x.startswith('target_') and x.endswith('Review!B4')) and
                x != 'non_target_changed:Review!B5' for x in errors)):
        raise ValueError('Independent saved-artifact verifier did not reject exactly wrong target')
    return {'task_score': 0, 'passed': False, 'wrong_target_changed_cells': 1,
            'intended_target_unchanged': True, 'independent_verifier': verdict,
            'saved_sha256': digest(saved)}


def audit_samples(*, root: Path, out: Path, filename: str, document_id: str) -> dict:
    lines = _private(out / 'samples.ndjson').splitlines()
    if not 1 <= len(lines) <= len(SAMPLE_DELAYS_MS):
        raise ValueError('Bounded raw TRAIN probe sample count changed')
    rows = [json.loads(x) for x in lines]
    frames = []
    modal = False; previous_end = None; prior_utc = None
    for index, row in enumerate(rows):
        frame = bound(root, row['frame']); frames.append(frame)
        before, after, start = (row.get(x) for x in
            ['monotonic_before_ns', 'monotonic_after_ns', 'probe_start_monotonic_ns'])
        try: utc = datetime.fromisoformat(row['captured_utc'])
        except (TypeError, ValueError): raise ValueError('Probe UTC timestamp invalid') from None
        stable = (row.get('window_id_before') == row.get('window_id_after') == document_id and
                  filename in row.get('window_title_before', '') and filename in row.get('window_title_after', ''))
        if (row.get('schema') != 'cua-native-wdi-v066-near-negative-no-action-sample-v7' or
                row.get('ordinal') != index or row.get('requested_delay_ms') != SAMPLE_DELAYS_MS[index] or
                row.get('full_frame_sha256') != digest(frame) or
                row.get('application_frame_sha256') != application_frame_digest(frame) or
                any(type(x) is not int for x in [before, after, start]) or
                not start <= before <= after or row.get('elapsed_ns') != after-start or
                start != rows[0]['probe_start_monotonic_ns'] or
                (previous_end is not None and before < previous_end) or
                utc.tzinfo is None or (prior_utc is not None and utc < prior_utc) or
                row.get('document_window_stable') is not stable):
            raise ValueError('Probe raw frame, timing, order or window evidence changed')
        for field in ['window_id_before', 'window_id_after', 'window_title_before', 'window_title_after']:
            if type(row.get(field)) is not str or row.get(field + '_sha256') != digest(row[field].encode()):
                raise ValueError('Probe raw window identity/hash changed')
        previous_end = after; prior_utc = utc
        if not stable:
            # A known Save As dialog is evidence of a real modal. Other window
            # changes stay a boundary stop without claiming a modal.
            titles = [row['window_title_before'], row['window_title_after']]
            modal = (row['window_id_before'] == row['window_id_after'] != document_id and
                     all('save as' in title.casefold() for title in titles))
            if index != len(rows)-1:
                raise ValueError('Probe continued after window/modal boundary')
    hashes = [application_frame_digest(x) for x in frames]
    material_return = False
    caret_transition = False
    for i in range(1, len(frames)):
        if hashes[i] != hashes[i-1] and adapter._single_caret_column(frames[i-1], frames[i]):
            caret_transition = True
        if i >= 2 and hashes[i] == hashes[i-2] != hashes[i-1] and not adapter._single_caret_column(frames[i-2], frames[i-1]):
            if i != len(frames)-1:
                raise ValueError('Probe continued after material oscillation')
            material_return = True
    over_wall = rows[-1]['elapsed_ns'] > MAX_PROBE_WALL_MS * 1_000_000
    if over_wall:
        classification = 'wall_bound_stop_infrastructure_invalid'
    elif modal:
        classification = 'real_modal_stop'
    elif any(not row['document_window_stable'] for row in rows):
        classification = 'other_window_boundary_stop_inconclusive'
    elif material_return:
        classification = 'real_material_oscillation_stop'
    elif len(rows) != len(SAMPLE_DELAYS_MS):
        raise ValueError('Probe was truncated without a bounded stop')
    elif caret_transition:
        classification = 'caret_only_probe_material_oscillation_inconclusive'
    else:
        classification = 'no_material_oscillation_observed_inconclusive'
    if len(rows) == len(SAMPLE_DELAYS_MS) and not over_wall and rows[-1]['elapsed_ns'] < sum(SAMPLE_DELAYS_MS)*1_000_000:
        raise ValueError('Requested no-action sample delays were not retained')
    return {'classification': classification, 'raw_samples': len(rows),
            'sample_ledger_sha256': digest(_private(out / 'samples.ndjson')),
            'material_oscillation_proven': classification == 'real_material_oscillation_stop'}


def review(*, freeze_path: Path, review_path: Path, permit_path: Path,
           independent_root_review_accepted: bool = False, review_note: str = '',
           active_probe=active_hashes) -> dict:
    if independent_root_review_accepted is not True or not review_note.strip():
        raise ValueError('Exact independent root review acceptance and private rationale required')
    value = validate_source(freeze_path)
    root = Path(value['output_root'])
    if (root.exists() or root.is_symlink() or review_path == permit_path or
            any(p.exists() or p.is_symlink() or not p.is_absolute() for p in [review_path, permit_path])):
        raise ValueError('Unused exclusive TRAIN review/permit/run roots required')
    active, count = active_probe()
    if active or count: raise ValueError('Provider must be active-zero at root review')
    if storage_audit(root.parent)['dispatch_storage_ready'] is not True:
        raise ValueError('Raw evidence storage unavailable at root review')
    private = {'schema': REVIEW_SCHEMA, 'status': 'root_reviewed_exact_six_train_guests_no_create',
               'freeze_sha256': digest(_private(freeze_path)), 'source_sha256s': value['source_sha256s'],
               'output_root': str(root), 'guest_maximum': MAX_GUESTS, 'lease_seconds_each': LEASE_SECONDS,
               'private_root_review_note': review_note, 'provider_active_at_review': 0,
               'prior_full_lease_accounting': value['prior_full_lease_accounting'],
               'storage_ready_at_review': True, 'same_intent_replay_authorized': False,
               'official_final_admissions': 0}
    review_sha = _write_new(review_path, private)
    permit = {k: private[k] for k in ['freeze_sha256', 'source_sha256s', 'output_root', 'guest_maximum',
              'lease_seconds_each', 'prior_full_lease_accounting', 'same_intent_replay_authorized', 'official_final_admissions']}
    permit.update(schema=PERMIT_SCHEMA, status='root_reviewed_exact_six_train_guests',
                  review_path=str(review_path), review_sha256=review_sha, dispatch_authorized=True)
    permit_sha = _write_new(permit_path, permit)
    return {'status': 'private_train_permit_written_without_provider_create',
            'review_sha256': review_sha, 'permit_sha256': permit_sha, 'official_final_admissions': 0}


def checked_permit(*, freeze_path: Path, permit_path: Path, value: dict) -> dict:
    permit = json.loads(_private(permit_path))
    review_path = Path(permit.get('review_path', ''))
    if not review_path.is_absolute(): raise ValueError('Exact independent root review path missing')
    review_raw = _private(review_path); reviewed = json.loads(review_raw)
    fields = {'freeze_sha256': digest(_private(freeze_path)), 'source_sha256s': value['source_sha256s'],
              'output_root': value['output_root'], 'guest_maximum': MAX_GUESTS, 'lease_seconds_each': LEASE_SECONDS,
              'prior_full_lease_accounting': value['prior_full_lease_accounting'],
              'same_intent_replay_authorized': False, 'official_final_admissions': 0}
    if (permit.get('schema') != PERMIT_SCHEMA or permit.get('status') != 'root_reviewed_exact_six_train_guests' or
            permit.get('dispatch_authorized') is not True or permit.get('review_sha256') != digest(review_raw) or
            reviewed.get('schema') != REVIEW_SCHEMA or reviewed.get('status') != 'root_reviewed_exact_six_train_guests_no_create' or
            not reviewed.get('private_root_review_note', '').strip() or reviewed.get('provider_active_at_review') != 0 or
            reviewed.get('storage_ready_at_review') is not True or
            any(permit.get(k) != v or reviewed.get(k) != v for k,v in fields.items())):
        raise ValueError('Exact root-reviewed TRAIN permit binding changed')
    return permit


class _Frame:
    def __init__(self, raw): self.raw = raw
    def screenshot(self): return self.raw


def _audit_actions(*, root: Path, receipt: dict, source: dict, oracle: dict, instruction: str) -> None:
    expected = actions_for(source['case'], oracle)
    steps = receipt.get('actor_steps', [])
    if len(steps) != len(expected): raise ValueError('GUI action count changed or continued after probe')
    previous = None
    for index, (step, minimal) in enumerate(zip(steps, expected)):
        observed, predispatch = bound(root, step['observation']), bound(root, step['predispatch'])
        if (step.get('step') != index or step.get('minimal_action') != minimal or step.get('status') != 'applied' or
                step.get('dispatch_type') != minimal['type'] or
                type(step.get('dispatch_before_monotonic_ns')) is not int or
                type(step.get('dispatch_after_monotonic_ns')) is not int or
                step['dispatch_after_monotonic_ns'] < step['dispatch_before_monotonic_ns'] or
                application_frame_digest(observed) != application_frame_digest(predispatch)):
            raise ValueError('Current-frame GUI action evidence changed')
        observation = adapter.observe(_Frame(observed), task_id=source['row']['task_id'],
             task_binding_sha256=source['row']['package_sha256'], instruction=instruction,
             step=index, previous_action_result=previous, max_actions=32)
        nonce = step.get('normalized_action', {}).get('frame_id')
        if type(nonce) is not str: raise ValueError('GUI envelope nonce missing')
        observation = replace(observation, frame_id=nonce)
        checked = normalize_model_action(json.dumps(minimal), observation, current_frame_id=nonce)
        if checked != step['normalized_action']: raise ValueError('Normalized GUI action envelope changed')
        previous = {'status': 'applied', 'code': 'ok'}
    for sample in receipt.get('physical_frame_resamples', []):
        bound(root, sample['observation']); bound(root, sample['changed'])


def _audit_profile(*, root: Path, receipt: dict, reference_path: Path) -> None:
    reference, reference_sha = validate_reference(reference_path)
    snapshots = receipt.get('task_profile_scoped_snapshots', [])
    if (len(snapshots) != 2 or receipt.get('task_profile_scoped_attested') is not True or
            receipt.get('profile_reference_private_sha256') != reference_sha):
        raise ValueError('Fresh scoped Calc profile attestation incomplete')
    days = []
    for snapshot in snapshots:
        manifest = json.loads(bound(root, snapshot['manifest'])); registry = bound(root, snapshot['registry'])
        bound(root, snapshot['visible_frame'])
        if scope.scoped_profile(manifest, registry) != reference['applications']['calc']:
            raise ValueError('Raw Calc profile differs from reviewed TRAIN reference')
        days.append(scope.tip_calendar_day(registry))
    floor = reference.get('current_public_tip_day')
    if floor is not None:
        probes = receipt.get('guest_calendar_probes', [])
        if len(probes) != 2 or days[0] != days[1] or days[0] < floor:
            raise ValueError('Raw guest date/profile continuity absent')
        observed = set()
        for probe in probes:
            values = bound(root, probe['raw']).decode().splitlines()
            if len(values) != 2: raise ValueError('Raw guest calendar probe invalid')
            observed.update((date.fromisoformat(x)-date(1970,1,1)).days for x in values)
        if days[0] not in observed: raise ValueError('Raw profile day differs from guest clock')


def audit(*, freeze_path: Path, run_path: Path, active_probe=active_hashes) -> dict:
    value = validate_source(freeze_path)
    root = Path(value['output_root']); run = json.loads(_private(run_path))
    if (run_path != root / 'run-receipt.json' or run.get('schema') != RUN_SCHEMA or
            run.get('freeze_sha256') != digest(_private(freeze_path)) or
            run.get('source_sha256s') != value['source_sha256s'] or run.get('guest_count_maximum') != MAX_GUESTS or
            run.get('same_intent_replay_authorized') is not False or run.get('official_final_admissions') != 0 or
            len(run.get('attempts', [])) != MAX_GUESTS):
        raise ValueError('Root-owned one-use six-guest TRAIN journal changed')
    permit_path = Path(run.get('permit_path', ''))
    if not permit_path.is_absolute() or digest(_private(permit_path)) != run.get('permit_sha256'):
        raise ValueError('Root-owned run exact TRAIN permit bytes changed')
    checked_permit(freeze_path=freeze_path, permit_path=permit_path, value=value)
    ids = set(); classifications = []; reset_count = 0; wrong_count = 0; modal_count = 0
    for ordinal in range(MAX_GUESTS):
        source = value['cases'][ordinal//2]; attempt = 'case' if ordinal%2 == 0 else 'cold-reset'
        out = root / f'{ordinal:02d}-{source["case"]}-{attempt}'
        intent_raw = _private(out/'intent.json'); intent = json.loads(intent_raw)
        receipt_raw = _private(out/'receipt.json'); receipt = json.loads(receipt_raw)
        journal = run['attempts'][ordinal]
        if (intent.get('schema') != INTENT_SCHEMA or receipt.get('schema') != RECEIPT_SCHEMA or
                intent.get('status') != 'recorded_before_provider_create' or
                intent.get('freeze_sha256') != run['freeze_sha256'] or intent.get('permit_sha256') != run.get('permit_sha256') or
                intent.get('same_intent_replay_authorized') is not False or receipt.get('intent_sha256') != digest(intent_raw) or
                receipt.get('provider_kind') != 'e2b_desktop' or journal.get('receipt_sha256') != digest(receipt_raw) or
                any(v.get('split') != 'train' or v.get('case') != source['case'] or v.get('attempt') != attempt or
                    v.get('ordinal') != ordinal or v.get('package_sha256') != source['row']['package_sha256'] or
                    v.get('input_sha256') != source['row']['input_sha256'] or v.get('lease_seconds') != LEASE_SECONDS or
                    v.get('official_final_admissions') != 0 for v in [intent, receipt]) or
                receipt.get('guest_content_attested') is not True or receipt.get('fresh_profile_absent') is not True or
                receipt.get('kill_returned') is not True or receipt.get('is_running_after_kill') is not False):
            raise ValueError('TRAIN intent, full lease, guest attestation, cleanup or journal changed')
        sid = receipt.get('sandbox_id_sha256')
        if type(sid) is not str or len(sid) != 64 or sid in ids:
            raise ValueError('All six TRAIN guests must be distinct')
        ids.add(sid)
        package_dir, baseline, oracle = admit._package(Path(value['candidate_root']), source['row'])
        _audit_profile(root=root, receipt=receipt, reference_path=Path(value['scoped_reference']))
        if attempt == 'cold-reset':
            if receipt.get('status') != 'cold_reset_observed' or receipt.get('actor_steps') != [] or bound(root, receipt['restored_artifact']) != baseline:
                raise ValueError('Fresh original-byte reset or no-action boundary changed')
            bound(root, receipt['cold_observation']); reset_count += 1; continue
        _audit_actions(root=root, receipt=receipt, source=source, oracle=oracle,
                       instruction=(package_dir/'actor_task.txt').read_text())
        if source['case'] == 'wrong-target':
            score = wrong_target_score(baseline, bound(root, receipt['saved_artifact']), oracle)
            if receipt.get('status') != 'wrong_target_saved_score_zero' or score != receipt.get('independent_saved_score'):
                raise ValueError('Independent saved wrong-target score changed')
            wrong_count += 1
        else:
            stimulus = receipt.get('trusted_negative_stimulus', {})
            if (stimulus.get('key') != TRUSTED_STIMULI[source['case']] or stimulus.get('status') != 'applied' or
                    stimulus.get('actor_step_count_before') != len(receipt['actor_steps']) or
                    type(stimulus.get('dispatch_before_monotonic_ns')) is not int or
                    type(stimulus.get('dispatch_after_monotonic_ns')) is not int or
                    stimulus['dispatch_after_monotonic_ns'] < stimulus['dispatch_before_monotonic_ns'] or
                    receipt.get('probe', {}).get('actor_actions_during_or_after_probe') != 0):
                raise ValueError('Restricted TRAIN stimulus or no-next-action boundary changed')
            bound(root, stimulus['before_frame'])
            result = audit_samples(root=root, out=out, filename=source['filename'], document_id=receipt['document_window_id'])
            rows = [json.loads(x) for x in _private(out/'samples.ndjson').splitlines()]
            if (rows[0]['probe_start_monotonic_ns'] < stimulus['dispatch_after_monotonic_ns'] or
                    result != receipt.get('probe_classification') or
                    result['sample_ledger_sha256'] != receipt['probe'].get('sample_ledger_sha256') or
                    result['raw_samples'] != receipt['probe'].get('raw_samples')):
                raise ValueError('Raw probe classification differs from saved receipt')
            if source['case'] == 'modal-stop':
                if result['classification'] != 'real_modal_stop' or receipt.get('status') != 'modal_stop_observed':
                    raise ValueError('Real modal stop evidence absent')
                modal_count += 1
            else:
                if receipt.get('status') != 'no_action_probe_audited': raise ValueError('No-action probe status changed')
                classifications.append(result['classification'])
    ledger = storage_audit(root, verify_all_bytes=True)
    active, count = active_probe()
    if active or count or ledger['unresolved_write_count']:
        raise ValueError('Raw retained storage or provider active-zero cleanup incomplete')
    oscillation = classifications == ['real_material_oscillation_stop']
    return {'schema': 'cua-native-wdi-v066-post-enter-near-negative-audit-public-v7',
            'status': 'train_near_negative_all_three_rejections_audited' if oscillation else 'train_saved_wrong_target_modal_reset_audited_oscillation_inconclusive',
            'source_scope': 'visible_train_only', 'wrong_target_saved_score_zero': wrong_count,
            'real_modal_stops': modal_count, 'fresh_original_byte_resets': reset_count,
            'distinct_sandbox_guests': len(ids), 'full_lease_intents_charged': MAX_GUESTS,
            'material_oscillation_proven': oscillation, 'no_action_probe_classifications': classifications,
            'provider_active_after': 0, 'same_intent_replay_authorized': False,
            'official_final_admissions': 0, 'official_model_results': 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('review', 'audit'))
    parser.add_argument('--freeze', type=Path, required=True); parser.add_argument('--review-out', type=Path)
    parser.add_argument('--permit-out', type=Path); parser.add_argument('--run', type=Path)
    parser.add_argument('--accept-independent-root-review', action='store_true')
    parser.add_argument('--private-review-note', default='')
    args = parser.parse_args()
    if args.mode == 'review':
        if args.review_out is None or args.permit_out is None: raise ValueError('Exact private review/permit paths required')
        result = review(freeze_path=args.freeze, review_path=args.review_out, permit_path=args.permit_out,
            independent_root_review_accepted=args.accept_independent_root_review, review_note=args.private_review_note)
    else:
        if args.run is None: raise ValueError('Exact root-owned TRAIN run journal required')
        result = audit(freeze_path=args.freeze, run_path=args.run)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__': main()
