"""Adversarial saved-OOXML controls for four additional TRAIN cases."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

from sec_excel_factory.audit_tax_train_transfer_two import mutate
from sec_excel_factory.verify_ooxml import load_xlsx
from sec_excel_factory.verify_train_remaining_four import (
    AFS_TARGETS, PENSION_TARGETS, verify,
)
from tools.sec_train_remaining_four_review_v1 import review as replay_review


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _private(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(raw)
    return sha256(raw).hexdigest()


def _modes(root: Path) -> None:
    if root.stat().st_mode & 0o777 != 0o700:
        raise ValueError('private_root_mode_not_0700')
    for child in root.rglob('*'):
        if child.is_symlink():
            raise ValueError('private_artifact_symlink_forbidden')
        expected = 0o700 if child.is_dir() else 0o600
        if child.stat().st_mode & 0o777 != expected:
            raise ValueError('private_artifact_mode_changed')


def _semantic_cases(profile: str) -> tuple:
    if profile == 'pension_full':
        return (
            ('wrong_period', 'Asset build', 'C5', "'Source facts'!B5"),
            ('swap_contributions', 'Asset build', 'C9', "'Source facts'!C8"),
            ('reverse_currency', 'Asset build', 'C10', "-'Source facts'!C10"),
            ('omit_settlements', 'Asset build', 'C13',
             'C5+C6+C7+C8+C9+C10+C11'),
            ('ignore_scenario', 'Pension summary', 'B9',
             "'Asset build'!C17"),
        )
    return (
        ('wrong_period', 'Fair bridge', 'C5', "'Source facts'!B5"),
        ('reverse_allowance', 'Fair bridge', 'C6',
         "-'Source facts'!C6"),
        ('omit_losses', 'Fair bridge', 'C9', 'C5+C6+C7'),
        ('omit_long_loss_position', 'Loss aging', 'C9', 'C5'),
        ('ignore_haircuts', 'AFS summary', 'B9',
         "'Fair bridge'!C10"),
    )


def audit_one(case: dict, workbooks: Path, controls: Path,
              manifest: dict) -> dict:
    index = case['case_index']
    case_dir = workbooks / f'case-{index:02d}'
    seed, positive = case_dir / 'seed.xlsx', case_dir / 'positive.xlsx'
    entry = [c for c in manifest['cases'] if c['case_index'] == index]
    if len(entry) != 1 or _sha(seed) != entry[0]['seed']['sha256'] or \
            _sha(positive) != entry[0]['positive']['sha256']:
        raise ValueError('workbook_manifest_hash_mismatch')
    targets = PENSION_TARGETS if case['profile'] == 'pension_full' else AFS_TARGETS
    if sorted(f'{s}!{a}' for s, a in targets) != \
            entry[0]['seed']['target_cells']:
        raise ValueError('frozen_target_repair_contract_changed')
    good = verify(positive, seed, case)
    faulty = verify(seed, seed, case)
    if not good['pass'] or faulty['pass'] or good['checked_targets'] != 12:
        raise ValueError('reference_or_faulty_seed_control_failed')
    old, *_ = load_xlsx(seed)
    fixed, *_ = load_xlsx(positive)
    control_dir = controls / f'case-{index:02d}'
    control_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    one_short = hardcode = 0
    for serial, (sheet, address) in enumerate(sorted(targets)):
        old_formula = old[sheet][address].formula
        saved = fixed[sheet][address].value
        if not old_formula or saved is None:
            raise ValueError('target_formula_or_saved_value_missing')
        near = control_dir / f'one-target-short-{serial:02d}.xlsx'
        mutate(positive, near, sheet, address,
               formula=old_formula, refresh_cache=True)
        verdict = verify(near, seed, case)
        if verdict['pass'] or not any('wrong_target_result:' in e
                                      for e in verdict['errors']):
            raise ValueError('one_target_short_accepted')
        one_short += 1
        static = control_dir / f'hardcoded-target-{serial:02d}.xlsx'
        mutate(positive, static, sheet, address,
               formula=saved, value=saved, refresh_cache=True)
        verdict = verify(static, seed, case)
        if verdict['pass'] or not any('wrong_target_result:' in e
                                      for e in verdict['errors']):
            raise ValueError('hardcoded_target_accepted')
        hardcode += 1
    semantic = 0
    for label, sheet, address, wrong in _semantic_cases(case['profile']):
        candidate = control_dir / f'semantic-{label}.xlsx'
        mutate(positive, candidate, sheet, address,
               formula=wrong, refresh_cache=True)
        verdict = verify(candidate, seed, case)
        if verdict['pass'] or not any('wrong_target_result:' in e
                                      for e in verdict['errors']):
            raise ValueError('semantic_negative_accepted')
        semantic += 1
    collateral = control_dir / 'collateral-source-edit.xlsx'
    value = fixed['Source facts']['C7'].value
    mutate(positive, collateral, 'Source facts', 'C7',
           value=str(float(value) + 1), refresh_cache=True)
    if verify(collateral, seed, case)['pass']:
        raise ValueError('collateral_source_edit_accepted')
    style = control_dir / 'style-change.xlsx'
    sheet, address = sorted(targets)[-1]
    mutate(positive, style, sheet, address, style_change=True)
    if verify(style, seed, case)['pass']:
        raise ValueError('target_style_change_accepted')
    summary = ('Pension summary' if case['profile'] == 'pension_full'
               else 'AFS summary')
    stale = control_dir / 'stale-display-cache.xlsx'
    value = fixed[summary]['B5'].value
    mutate(positive, stale, summary, 'B5', value=str(float(value) + 100))
    if verify(stale, seed, case)['pass']:
        raise ValueError('stale_display_cache_accepted')
    missing = control_dir / 'missing-target-cache.xlsx'
    mutate(positive, missing, summary, 'B9', remove_cache=True)
    verdict = verify(missing, seed, case)
    if verdict['pass'] or not any('missing_saved_numeric_formula_cache:' in e
                                  for e in verdict['errors']):
        raise ValueError('missing_display_cache_accepted')
    reset = control_dir / 'fresh-reset-seed.xlsx'
    shutil.copyfile(seed, reset)
    os.chmod(reset, 0o600)
    if _sha(reset) != _sha(seed) or verify(reset, seed, case)['pass']:
        raise ValueError('fresh_reset_not_byte_exact_faulty_seed')
    return {'case_index': index, 'profile': case['profile'],
            'reference_pass': True, 'faulty_seed_rejected': True,
            'target_count': 12,
            'one_target_short_rejected': one_short,
            'hardcoded_target_rejected': hardcode,
            'semantic_negatives_rejected': semantic,
            'collateral_source_edit_rejected': True,
            'style_change_rejected': True,
            'stale_cache_rejected': True,
            'missing_cache_rejected': True,
            'fresh_reset_byte_exact': True,
            'counterfactual_replays': good['counterfactual_replays'],
            'seed_sha256': _sha(seed),
            'positive_sha256': _sha(positive)}


def audit(review_path: Path, source_plan: Path,
          reviewed_cards: Path, workbooks: Path,
          controls: Path) -> dict:
    private = json.loads(review_path.read_bytes())
    if private.get('schema') != \
            'envloop.sec_excel_train_remaining_four_review.private.v1':
        raise ValueError('private_source_review_schema_changed')
    if replay_review(Path(private['raw_source_root']), source_plan,
                     reviewed_cards) != private:
        raise ValueError('review_not_reconstructible_from_frozen_sec_bytes')
    manifest_path = workbooks / 'workbooks-manifest.private.json'
    manifest = json.loads(manifest_path.read_bytes())
    if manifest['review_sha256'] != _sha(review_path):
        raise ValueError('review_workbook_manifest_binding_changed')
    controls.mkdir(parents=True, exist_ok=False, mode=0o700)
    cases = [audit_one(c, workbooks, controls, manifest)
             for c in private['cases']]
    _modes(workbooks.parent)
    return {'schema':
            'envloop.sec_excel_train_remaining_four_offline_audit.private.v1',
            'status': 'source_replay_and_offline_ooxml_controls_passed',
            'source_plan_sha256': _sha(source_plan),
            'skill_cards_sha256': _sha(reviewed_cards),
            'review_sha256': _sha(review_path),
            'manifest_sha256': _sha(manifest_path),
            'reviewer_source_sha256': private['reviewer_source_sha256'],
            'scope_test_source_sha256': private['scope_test_source_sha256'],
            'cases': cases, 'model_calls': 0,
            'excel_web_gui_controls': 0,
            'official_final_admissions': 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--review', type=Path, required=True)
    ap.add_argument('--source-plan', type=Path, required=True)
    ap.add_argument('--reviewed-cards', type=Path, required=True)
    ap.add_argument('--workbooks', type=Path, required=True)
    ap.add_argument('--controls', type=Path, required=True)
    ap.add_argument('--private-out', type=Path, required=True)
    ap.add_argument('--public-out', type=Path, required=True)
    args = ap.parse_args()
    result = audit(args.review, args.source_plan, args.reviewed_cards,
                   args.workbooks, args.controls)
    private_sha = _private(args.private_out, result)
    public = {
        'schema':
            'envloop.sec_excel_train_remaining_four_offline_audit.public.v1',
        'status': result['status'],
        'source_plan_sha256': result['source_plan_sha256'],
        'reviewed_skill_cards_sha256': result['skill_cards_sha256'],
        'private_review_sha256': result['review_sha256'],
        'private_workbook_manifest_sha256': result['manifest_sha256'],
        'private_offline_audit_sha256': private_sha,
        'reviewer_source_sha256': result['reviewer_source_sha256'],
        'dimension_scope_test_sha256': result['scope_test_source_sha256'],
        'train_source_packages': len(result['cases']),
        'source_distinct_train_issuers': len(result['cases']),
        'source_graph_families': 2,
        'seed_workbooks': len(result['cases']),
        'reference_workbooks': len(result['cases']),
        'pension_sheets_per_workbook': 6,
        'afs_sheets_per_workbook': 8,
        'formula_repairs_per_case': 12,
        'reference_saved_ooxml_pass': sum(c['reference_pass']
                                         for c in result['cases']),
        'faulty_seeds_rejected': sum(c['faulty_seed_rejected']
                                     for c in result['cases']),
        'one_target_short_rejected': sum(c['one_target_short_rejected']
                                         for c in result['cases']),
        'hardcoded_target_rejected': sum(c['hardcoded_target_rejected']
                                         for c in result['cases']),
        'semantic_negatives_rejected': sum(c['semantic_negatives_rejected']
                                            for c in result['cases']),
        'source_counterfactual_replays': sum(c['counterfactual_replays']
                                              for c in result['cases']),
        'collateral_source_edits_rejected': 4,
        'style_edits_rejected': 4,
        'stale_display_caches_rejected': 4,
        'missing_display_caches_rejected': 4,
        'byte_exact_fresh_resets': 4,
        'pension_dimension_member_counts': [1, 2],
        'afs_aggregate_dimension_member_count': 0,
        'model_calls': 0, 'excel_web_gui_controls': 0,
        'official_final_admissions': 0,
        'claim_boundary': 'Offline TRAIN source-transfer and saved-OOXML controls only. Original Excel-for-the-web saved readback/reset, model effects, and formal admissions remain pending.',
    }
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    args.public_out.write_text(json.dumps(public, indent=2,
                                          sort_keys=True) + '\n')
    print(json.dumps({'status': 'four_remaining_source_offline_controls_passed',
                      'private_audit_sha256': private_sha,
                      'public_path': str(args.public_out),
                      'reference_pass': public['reference_saved_ooxml_pass'],
                      'one_short_rejected': public['one_target_short_rejected']}))


if __name__ == '__main__':
    main()
