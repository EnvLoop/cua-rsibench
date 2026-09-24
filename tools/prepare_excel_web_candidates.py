"""Offline source audit; produces candidates, never a GUI score or ready benchmark."""
import argparse
from collections import Counter
import io
import json
from pathlib import Path
import re
import tarfile
import xml.etree.ElementTree as ET

from excel_web_ooxml import MAIN, digest, read_workbook, task_50250, wrong_h2_fixture, value_at

SOURCE_SHA = '10ef893dd29cb13ab97143ea787e68cdc9574a13873ab9a54e50b31dc03fc949'
DATASET_MEMBER = 'spreadsheetbench_verified_400/dataset.json'
SUPPORT_URL = 'https://support.microsoft.com/en-us/excel/differences-between-using-a-workbook-in-the-browser-and-in-excel'
SENSITIVE = re.compile(r'\b(VBA|macros?|UDF|ActiveX|add[- ]?ins?|Solver|Goal Seek|Power\s*Query|Power\s*Pivot|external|hyperlinks?|print|PDF|charts?|pivot)\b', re.I)
TIME_DEPENDENT = re.compile(r'\b(TODAY|NOW|RAND|RANDBETWEEN)\s*\(|\b(current day|current date|today|circular reference)\b', re.I)
FORMATTING = re.compile(r'\b(highlight|formatting|font|bold|background color|fill color|colour|color|border|conditional format)\b', re.I)
CJK = re.compile(r'[\u3400-\u9fff\uf900-\ufaff]')
RANGE = re.compile(r"^(?:(?:'[^']+'|[^!,]+)!)?\$?[A-Z]+\$?[1-9][0-9]*(?::\$?[A-Z]+\$?[1-9][0-9]*)?$", re.I)


def target_cells(row, initial):
    position = row['answer_position'].replace('$', '')
    sheet = row.get('answer_sheet') or next(iter(initial['sheets']))
    if '!' in position:
        sheet, position = position.split('!', 1)
        sheet = sheet.strip("'")
    pieces = position.upper().split(':')
    def coordinate(value):
        match = re.fullmatch(r'([A-Z]+)([1-9][0-9]*)', value)
        if not match:
            raise ValueError('invalid target range')
        column = 0
        for char in match[1]:
            column = column * 26 + ord(char) - 64
        return column, int(match[2])
    left, top = coordinate(pieces[0])
    right, bottom = coordinate(pieces[-1])
    if right < left or bottom < top or (right-left+1)*(bottom-top+1) > 100000:
        raise ValueError('oversized or reversed target range')
    result = []
    for col in range(left, right + 1):
        name, value = '', col
        while value:
            value, rem = divmod(value-1, 26)
            name = chr(65+rem) + name
        result.extend(name+str(number) for number in range(top, bottom+1))
    return sheet, result


def workbook_features(data):
    book = read_workbook(data)
    flags = []
    names = book['members']
    markers = {'vbaProject': 'vba_binary', 'activeX': 'activex', 'ctrlProps': 'form_controls',
               'externalLinks': 'external_links', 'connections.xml': 'data_connections',
               'queryTables': 'query_tables', 'pivotTables': 'pivot_tables',
               'embeddings': 'embedded_objects', 'xmlMaps': 'xml_maps', '_xmlsignatures': 'digital_signatures'}
    for marker, flag in markers.items():
        if any(marker in name for name in names):
            flags.append(flag)
    functions = set()
    formulas = 0
    missing_caches = 0
    for sheet, content in book['sheets'].items():
        if CJK.search(sheet):
            flags.append('non_english_sheet_name')
        for cell in content['cells'].values():
            if cell['type'] == 'text' and CJK.search(cell['value'] or ''):
                flags.append('non_english_cell_text')
            if cell['formula'] is not None:
                formulas += 1
                missing_caches += not cell['formula_cache_present']
                text = cell['formula'][2]
                functions.update(re.findall(r'([A-Za-z_][A-Za-z0-9_.]*)\s*\(', text))
                if TIME_DEPENDENT.search(text):
                    flags.append('volatile_time_or_random_formula')
                if re.search(r'\b(INFO|RTD|CALL|REGISTER\.ID|WEBSERVICE)\s*\(', text, re.I):
                    flags.append('desktop_or_external_function')
        for tag in ('sheetProtection', 'legacyDrawing', 'oleObjects'):
            if any(True for _ in ET.fromstring(names[content['path']]).iter(MAIN + tag)):
                flags.append(tag)
    root = ET.fromstring(names['xl/workbook.xml'])
    if root.find(MAIN + 'workbookProtection') is not None:
        flags.append('workbookProtection')
    return {'flags': sorted(set(flags)), 'sheets': list(book['sheets']),
            'formula_count': formulas, 'formula_caches_missing': missing_caches,
            'formula_functions': sorted(functions),
            'cell_count': sum(len(s['cells']) for s in book['sheets'].values())}


def analyze(archive_path):
    payload = Path(archive_path).read_bytes()
    if digest(payload) != SOURCE_SHA:
        raise ValueError('not the pinned verified-400 archive')
    records = []
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
        members = {m.name: m for m in archive.getmembers() if m.isfile()}
        raw_dataset = archive.extractfile(DATASET_MEMBER).read()
        rows = json.loads(raw_dataset)
        if len(rows) != 400:
            raise ValueError('unexpected source task count')
        for row in rows:
            ident = str(row['id'])
            prefix = 'spreadsheetbench_verified_400/spreadsheet/' + ident + '/'
            files = {name: archive.extractfile(member).read() for name, member in members.items()
                     if name.startswith(prefix) and name.endswith('.xlsx')}
            inputs = [name for name in files if name.endswith(('_init.xlsx', '/initial.xlsx'))]
            goldens = [name for name in files if name.endswith(('_golden.xlsx', '/golden.xlsx'))]
            if len(inputs) != 1 or len(goldens) != 1:
                raise ValueError('task lacks exactly one source/reference pair: ' + ident)
            inspected = {}
            for role, name in [('input', inputs[0]), ('golden', goldens[0])]:
                try:
                    inspected[role] = workbook_features(files[name])
                except (ValueError, KeyError, ET.ParseError) as exc:
                    inspected[role] = {'flags': ['ooxml_parse_requires_review'], 'sheets': [],
                                       'error_type': type(exc).__name__}
            reasons = []
            if row.get('exclude'):
                reasons.append('source_marked_exclude')
            if SENSITIVE.search(row['instruction']):
                reasons.append('feature_mentioned_requires_review')
            if TIME_DEPENDENT.search(row['instruction']):
                reasons.append('time_or_iteration_dependent_instruction')
            if FORMATTING.search(row['instruction']):
                reasons.append('formatting_reward_not_qualified')
            if CJK.search(row['instruction']):
                reasons.append('non_english_instruction')
            if row['instruction_type'] != 'Cell-Level Manipulation':
                reasons.append('sheet_restructuring_requires_separate_oracle')
            if not RANGE.fullmatch(row['answer_position']):
                reasons.append('complex_target_range_requires_review')
            if len(inspected['input']['sheets']) > 1 and not row.get('answer_sheet') and '!' not in row['answer_position']:
                reasons.append('multisheet_target_not_explicit')
            reasons.extend('input:' + f for f in inspected['input']['flags'])
            reasons.extend('golden:' + f for f in inspected['golden']['flags'])
            target_check = {'status': 'not_checked'}
            if RANGE.fullmatch(row['answer_position']) and inspected['input']['sheets'] and inspected['golden']['sheets']:
                try:
                    initial = read_workbook(files[inputs[0]])
                    golden = read_workbook(files[goldens[0]])
                    sheet, targets = target_cells(row, initial)
                    before = [value_at(initial, sheet, cell) for cell in targets]
                    after = [value_at(golden, sheet, cell) for cell in targets]
                    equal = all((a['type'], a['value']) == (b['type'], b['value']) for a, b in zip(before, after))
                    target_check = {'status': 'inspected', 'sheet': sheet, 'cell_count': len(targets),
                                    'initial_matches_reference_values': equal,
                                    'reference_formula_cache_missing': any(not c['formula_cache_present'] for c in after),
                                    'reference_contains_error': any(c['type'] == 'error' for c in after)}
                    if equal:
                        reasons.append('initial_already_matches_reference_values')
                    if target_check['reference_formula_cache_missing']:
                        reasons.append('reference_target_formula_cache_missing')
                    if target_check['reference_contains_error']:
                        reasons.append('reference_target_error_requires_review')
                except (ValueError, KeyError):
                    target_check = {'status': 'target_mapping_requires_review'}
                    reasons.append('target_mapping_requires_review')
            records.append({'task_id': ident, 'source_cluster_id': 'question:' + ident.split('-', 1)[0],
                'cluster_caveat': 'Question ID prefix only; shared workbook/content families still need deduplication.',
                'instruction': row['instruction'], 'instruction_type': row['instruction_type'],
                'answer_position': row['answer_position'], 'answer_sheet': row.get('answer_sheet'),
                'default_answer_sheet': next(iter(inspected['input']['sheets']), None),
                'source_record_sha256': digest(json.dumps(row, sort_keys=True).encode()),
                'source_exclusion': row.get('exclude'),
                'files': [{'role': role, 'archive_member': name, 'sha256': digest(files[name]), 'bytes': len(files[name])}
                          for role, name in [('input', inputs[0]), ('golden', goldens[0])]],
                'workbook_inspection': inspected,
                'target_readback': target_check,
                'compatibility': 'plausible_core_excel_web_operations' if not reasons else 'excluded_from_first_100_pending_review',
                'screening_reasons': sorted(set(reasons)), 'gui_verified': False,
                'operation_basis': 'Cell value/formula manipulation with no detected dependency on excluded web features; static screening only.'})
    return records, digest(raw_dataset)


def prepare(archive_path, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    records, dataset_sha = analyze(archive_path)
    eligible = sorted([r for r in records if not r['screening_reasons']],
                      key=lambda r: digest(('excel-web-offline-v1:23:' + r['task_id']).encode()))
    if len(eligible) < 100:
        raise ValueError('fewer than 100 statically eligible candidates: ' + str(len(eligible)))
    selected = eligible[:100]
    # Representative is explicit qualification evidence, not forced into the100.
    representative = next(r for r in records if r['task_id'] == '50250')
    if representative['screening_reasons']:
        raise ValueError('representative is not eligible')
    manifest = {'schema': 'excel-web-static-candidates-v1', 'status': '100 offline candidates; zero GUI-qualified tasks',
        'source': {'archive_sha256': SOURCE_SHA, 'dataset_sha256': dataset_sha,
                   'dataset_commit': 'ab0b742b0fc95b946f212d80ac7771b5531272e4',
                   'code_commit': '49b73a94775fb489063f60ca1865e3a650079a79',
                   'url': 'https://huggingface.co/datasets/KAKA22/SpreadsheetBench/tree/ab0b742b0fc95b946f212d80ac7771b5531272e4',
                   'license': 'CC-BY-SA-4.0 as declared by upstream'},
        'counts': {'source_tasks': len(records), 'source_workbooks': 2 * len(records),
                   'source_explicit_exclusions': sum(bool(r['source_exclusion']) for r in records),
                   'statically_eligible': len(eligible), 'selected_candidates': 100, 'gui_qualified': 0},
        'selection_rule': 'First100 by sha256(excel-web-offline-v1:23:<task_id>) among conservatively screened cell-level candidates.',
        'not_an_experimental_split': True, 'requested_full_scale_protocol': {'selection': 100, 'final': 100, 'official_repetitions': 1},
        'split_blocker': 'These100 are candidate inventory only; no100+100source-disjoint, reset-qualified split is claimed.',
        'candidates': selected,
        'unsupported_or_unknown': {'unsupported': ['VBA execution', 'legacy XLM macro sheets', 'visible ActiveX/form controls', 'XML maps', 'digital signatures'],
            'conditional_or_unverified': ['external references and connections', 'Power Query/Power Pivot entitlement and refresh', 'pivot/chart operation specifics', 'worksheet protection', 'font rendering', 'volatile date/time functions', 'formatting equivalence', 'native recalculation and save/readback'],
            'source': SUPPORT_URL, 'feature_mentions_are_review_flags_not_proof_of_impossibility': True},
        'oracle_audit': {'upstream_path': 'evaluation/evaluation.py',
            'findings': ['Legacy evaluator expects three input/answer pairs; Verified400 has one init/golden pair.',
                         'answer_sheet metadata is ignored when answer_position lacks an explicit sheet.',
                         'data_only cached values are used; numeric values are rounded to two decimals.',
                         'Fill/font comparisons are commented out; unrelated cells and GUI provenance are not checked.'],
            'unchanged_upstream_oracle_accepted': False},
        'admission_gates': ['Owner verifies Microsoft account and Excel web availability.', 'Fresh workbook upload/reset and GUI open succeeds.',
            'Actor uses only declared GUI actions.', 'Save completes; downloaded file is bound to job and cloud item/version.',
            'Required recalculation is observed in actual Excel, not inferred from cached XML.', 'Task-specific output and preservation checks pass.',
            'Independent negative and no-op controls fail; source families are split before search.']}
    (out / 'candidate-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    inventory = {'schema': 'excel-web-source-screening-v1', 'counts': manifest['counts'],
                 'reason_counts': dict(Counter(reason for r in records for reason in r['screening_reasons'])), 'records': records}
    (out / 'all-400-screening.json').write_text(json.dumps(inventory, indent=2) + '\n')
    fixture = out / 'oracle-50250'
    fixture.mkdir(exist_ok=True)
    with tarfile.open(archive_path, 'r:gz') as archive:
        files = {r['role']: archive.extractfile(r['archive_member']).read() for r in representative['files']}
    (fixture / 'source-input.xlsx').write_bytes(files['input'])
    (fixture / 'source-golden.xlsx').write_bytes(files['golden'])
    wrong = wrong_h2_fixture(files['golden'])
    (fixture / 'wrong-result-negative.xlsx').write_bytes(wrong)
    evidence = {'schema': 'excel-web-offline-oracle-check-v1', 'task': representative,
                'positive_is_supplied_reference_not_agent_output': True,
                'positive': task_50250(files['input'], files['golden']),
                'wrong_result_negative': task_50250(files['input'], wrong),
                'unchanged_input_negative': task_50250(files['input'], files['input']),
                'login_performed': False, 'model_calls': 0, 'gui_success_claim': False}
    if not evidence['positive']['artifact_value_pass'] or evidence['wrong_result_negative']['artifact_value_pass'] or evidence['unchanged_input_negative']['artifact_value_pass']:
        raise ValueError('offline oracle controls did not behave as expected')
    (fixture / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')
    return {'counts': manifest['counts'], 'oracle_controls_pass': True, 'gui_success_claim': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.archive, args.out)))
