"""Audit a pinned SpreadsheetBench 2 archive and plan a hard Excel candidate split.

This is an offline source-family split, not a web-compatibility certificate, a
sealed exam, or a scored run. No source workbooks, task instructions, or answers
are copied to the output.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from excel_web_ooxml import read_workbook


SOURCE_SHA256 = '17147ef9578cd57ce76c9a719d19da7821f3e5cb0d8f776c820f699fdcdb761c'
SOURCE_REVISION = '5a2215ed4121945ab09d8723df2995602090b042'
SEED = 'cua-hard-excel-v2-family-split-2026-09-24'
QUOTAS = {'Financial_Model': {'final': 10, 'selection': 2},
          'Debugging': {'final': 5, 'selection': 1}}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def manifest_path(category: str) -> str:
    return f'spreadsheetbench-v2/{category}/dataset.json'


def archive_path(category: str, relative: str) -> str:
    if relative.startswith('/') or '..' in Path(relative).parts:
        raise ValueError('unsafe source member')
    return f'spreadsheetbench-v2/{category}/{relative}'


def structural_features(raw: bytes) -> dict:
    book = read_workbook(raw)
    cells = [cell for sheet in book['sheets'].values()
             for cell in sheet['cells'].values()]
    members = book['members']
    return {
        'sheets': len(book['sheets']),
        'instantiated_cells': len(cells),
        'formula_cells': sum(cell['formula'] is not None for cell in cells),
        'external_links': any('externalLinks/' in name for name in members),
        'data_connections': any(name.endswith('/connections.xml') for name in members),
        'vba_binary': any(name.endswith('vbaProject.bin') for name in members),
    }


def screen(features: dict) -> list[str]:
    """A structural triage, with a provisional UI-volume cap, not a difficulty score."""
    reasons = []
    if features['sheets'] < 7:
        reasons.append('fewer_than_7_sheets')
    if features['formula_cells'] < 1000:
        reasons.append('fewer_than_1000_formula_cells')
    if features['instantiated_cells'] > 400000:
        reasons.append('over_400000_instantiated_cells_requires_separate_ui_budget')
    for key in ('external_links', 'data_connections', 'vba_binary'):
        if features[key]:
            reasons.append(key + '_requires_separate_track')
    return reasons


def choose_families(families: dict[str, dict], quotas: dict = QUOTAS) -> dict:
    """Select whole workbook families, leaving no family across splits."""
    result = {'provisional_final': [], 'selection': []}
    for category, counts in quotas.items():
        eligible = [family for family in families.values()
                    if family['category'] == category and not family['screening_reasons']]
        eligible.sort(key=lambda family: sha(f'{SEED}:{category}:{family["family_id"]}'.encode()))
        need = counts['final'] + counts['selection']
        if len(eligible) < need:
            raise ValueError(f'{category}: {len(eligible)} eligible families; {need} required')
        result['provisional_final'].extend(eligible[:counts['final']])
        result['selection'].extend(eligible[counts['final']:need])
    return result


def audit_archive(path: Path) -> dict:
    raw = path.read_bytes()
    if sha(raw) != SOURCE_SHA256:
        raise ValueError('archive is not the pinned SpreadsheetBench 2 source')
    families: dict[str, dict] = {}
    with ZipFile(path) as archive:
        for category, expected in (('Financial_Model', 100), ('Debugging', 100)):
            manifest = archive.read(manifest_path(category))
            rows = json.loads(manifest)
            if len(rows) != expected:
                raise ValueError(f'{category}: unexpected source task count')
            grouped = defaultdict(list)
            for row in rows:
                grouped[row['golden_response_path']].append(row)
            expected_family_size = 5 if category == 'Financial_Model' else 10
            for golden, members in sorted(grouped.items()):
                if len(members) != expected_family_size:
                    raise ValueError(f'{category}: unexpected family size')
                first = members[0]
                input_raw = archive.read(archive_path(category, first['spreadsheet_path']))
                features = structural_features(input_raw)
                family_id = f'{category}:{golden}'
                task_rows = []
                for row in members:
                    workbook_raw = archive.read(archive_path(category, row['spreadsheet_path']))
                    task_rows.append({
                        'task_id': f'{category}:{row["id"]}',
                        'input_sha256': sha(workbook_raw),
                        'instruction_sha256': sha(row['instruction'].encode('utf-8')),
                        'family_id': family_id,
                    })
                families[family_id] = {
                    'family_id': family_id, 'category': category,
                    'source_task_count': len(members),
                    'features_first_input': features,
                    'screening_reasons': screen(features),
                    'tasks': task_rows,
                }
    chosen = choose_families(families)
    splits = {name: [task for family in rows for task in family['tasks']]
              for name, rows in chosen.items()}
    final_groups = {row['family_id'] for row in splits['provisional_final']}
    selection_groups = {row['family_id'] for row in splits['selection']}
    if final_groups & selection_groups or len(splits['provisional_final']) != 100 or len(splits['selection']) != 20:
        raise AssertionError('source-family split is invalid')
    return {
        'schema': 'cua-hard-excel-v2-offline-split-v1',
        'status': 'offline_candidates_only_zero_gui_qualified',
        'source': {'archive_sha256': SOURCE_SHA256, 'revision': SOURCE_REVISION,
                   'dataset_url': 'https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2',
                   'license_conflict': 'Paper CC-BY-SA-4.0; dataset card MIT; do not redistribute assets'},
        'triage_rule': {'minimum_sheets': 7, 'minimum_existing_formula_cells': 1000,
                        'provisional_maximum_instantiated_cells': 400000,
                        'rationale': 'Source complexity and first GUI-volume screen only; no task is admitted by these numbers'},
        'counts': {'published_task_instances': 200, 'published_base_workbook_families': len(families),
                   'eligible_families': sum(not family['screening_reasons'] for family in families.values()),
                   'provisional_final_tasks': len(splits['provisional_final']),
                   'provisional_final_families': len(final_groups),
                   'selection_tasks': len(splits['selection']),
                   'selection_families': len(selection_groups),
                   'gui_qualified_tasks': 0},
        'qualification_required': ['individual Excel-web untouched round trip',
                                   'visible GUI positive completion',
                                   'independent saved-artifact and hidden-perturbation oracle',
                                   'wrong-answer and unrelated-change rejection',
                                   'fresh reset and source-family isolation',
                                   'license and public-answer leakage review'],
        'families': [{key: value for key, value in family.items() if key != 'tasks'}
                     for family in sorted(families.values(), key=lambda row: row['family_id'])],
        'task_sets': splits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit_archive(args.archive)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    main()
