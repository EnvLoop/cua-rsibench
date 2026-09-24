"""Independent, read-only OOXML inspection and a narrow task-50250 oracle.

No spreadsheet engine is invoked. Cached values are observations, never evidence
of recalculation or GUI execution. This module is outside the frozen v0.5 runtime.
"""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile

MAIN = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
MAX_UNPACKED = 100_000_000


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package(data):
    """Read a bounded ZIP without extracting paths or resolving external links."""
    archive = zipfile.ZipFile(io.BytesIO(data))
    infos = archive.infolist()
    names = [entry.filename for entry in infos]
    if len(names) != len(set(names)) or sum(entry.file_size for entry in infos) > MAX_UNPACKED:
        raise ValueError('duplicate or oversized OOXML package')
    if any(PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts for name in names):
        raise ValueError('unsafe OOXML member')
    result = {entry.filename: archive.read(entry) for entry in infos if not entry.is_dir()}
    if any(b'<!DOCTYPE' in value or b'<!ENTITY' in value for name, value in result.items() if name.endswith('.xml')):
        raise ValueError('DTD or entity definitions are not accepted')
    return result


def semantic_xml(node):
    return (node.tag, tuple(sorted(node.attrib.items())), node.text or '',
            tuple(semantic_xml(child) for child in node))


def read_workbook(data):
    members = package(data)
    root = ET.fromstring(members['xl/workbook.xml'])
    relations = ET.fromstring(members['xl/_rels/workbook.xml.rels'])
    targets = {}
    for row in relations:
        if row.get('TargetMode') == 'External':
            continue
        target = row.get('Target', '')
        targets[row.get('Id')] = target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/' + target)
    shared = []
    if 'xl/sharedStrings.xml' in members:
        for row in ET.fromstring(members['xl/sharedStrings.xml']):
            shared.append(''.join(node.text or '' for node in row.iter(MAIN + 't')))
    sheets = {}
    for entry in root.find(MAIN + 'sheets'):
        name = entry.get('name')
        if name in sheets:
            raise ValueError('duplicate worksheet name')
        path = targets[entry.get(REL + 'id')]
        tree = ET.fromstring(members[path])
        cells = {}
        for cell in tree.iter(MAIN + 'c'):
            coordinate = cell.get('r')
            if coordinate in cells or not re.fullmatch(r'[A-Z]+[1-9][0-9]*', coordinate or ''):
                raise ValueError('invalid or duplicate cell coordinate')
            kind = cell.get('t', 'n')
            raw = cell.findtext(MAIN + 'v')
            formula = cell.find(MAIN + 'f')
            if kind == 's':
                value = shared[int(raw)] if raw is not None else None
                value_type = 'text'
            elif kind == 'inlineStr':
                value = ''.join(node.text or '' for node in cell.iter(MAIN + 't'))
                value_type = 'text'
            elif raw is None or (kind == 'n' and raw == ''):
                value, value_type = None, 'blank'
            elif kind in ('str', 'd', 'e', 'b'):
                value, value_type = raw, {'str': 'text', 'd': 'iso_date', 'e': 'error', 'b': 'boolean'}[kind]
            else:
                try:
                    number = Decimal(raw)
                except InvalidOperation as exc:
                    raise ValueError('invalid numeric cell') from exc
                if not number.is_finite():
                    raise ValueError('nonfinite numeric cell')
                value, value_type = str(number.normalize()), 'number'
            cells[coordinate] = {'type': value_type, 'value': value,
                                 'formula': None if formula is None else semantic_xml(formula),
                                 'formula_cache_present': formula is None or (raw is not None and (kind != 'n' or raw != '')),
                                 'style_index': cell.get('s', '0')}
        sheets[name] = {'path': path, 'cells': cells,
                        'merged_ranges': sorted(node.get('ref') for node in tree.iter(MAIN + 'mergeCell'))}
    return {'sheets': sheets, 'members': members,
            'date1904': (root.find(MAIN + 'workbookPr') is not None and
                         root.find(MAIN + 'workbookPr').get('date1904') in ('1', 'true'))}


def value_at(book, sheet, cell):
    return book['sheets'][sheet]['cells'].get(cell, {'type': 'blank', 'value': None, 'formula': None,
                                                  'formula_cache_present': True, 'style_index': '0'})


def task_50250(input_data, output_data):
    """Derive the requested conditional sum from the input, not its golden answer."""
    initial, output = read_workbook(input_data), read_workbook(output_data)
    if len(initial['sheets']) != 1:
        raise ValueError('task-50250 requires its single-sheet source fixture')
    sheet = next(iter(initial['sheets']))
    key = value_at(initial, sheet, 'G2')
    if key['type'] != 'text' or key['value'] != 'sela':
        raise ValueError('unexpected task-50250 source key')
    expected = Decimal(0)
    for row in range(1, 18):
        match = any(value_at(initial, sheet, f'{column}{row}')['value'] == key['value']
                    for column in ('A', 'B'))
        if match:
            for column in ('C', 'D', 'E'):
                cell = value_at(initial, sheet, f'{column}{row}')
                if cell['type'] == 'number':
                    expected += Decimal(cell['value'])
    errors = []
    if list(initial['sheets']) != list(output['sheets']) or initial['date1904'] != output['date1904']:
        errors.append('worksheet_identity_or_date_system_changed')
    if sheet not in output['sheets']:
        errors.append('target_sheet_missing')
    else:
        actual = value_at(output, sheet, 'H2')
        if actual['type'] != 'number' or Decimal(actual['value']) != expected:
            errors.append('H2_value_mismatch')
        if not actual['formula_cache_present']:
            errors.append('H2_formula_cache_missing')
        a, b = initial['sheets'][sheet], output['sheets'][sheet]
        if a['merged_ranges'] != b['merged_ranges']:
            errors.append('merged_ranges_changed')
        for coordinate in sorted(set(a['cells']) | set(b['cells'])):
            if coordinate == 'H2':
                continue
            left, right = value_at(initial, sheet, coordinate), value_at(output, sheet, coordinate)
            # Style index is not a semantic style: Excel may renumber styles.
            # Preserve all non-target values/formulas; formatting not claimed.
            if any(left[k] != right[k] for k in ('type', 'value', 'formula')):
                errors.append('unrelated_cell_changed:' + coordinate)
    return {'oracle': 'independent-ooxml-task-50250-v1', 'task_id': '50250',
            'artifact_value_pass': not errors, 'expected_H2': str(expected), 'errors': errors,
            'input_sha256': digest(input_data), 'output_sha256': digest(output_data),
            'gui_execution_verified': False, 'native_recalculation_verified': False,
            'coverage': ['H2 numeric conditional sum', 'other cell values and formulas', 'sheet identity', 'merged ranges', 'date system'],
            'not_covered': ['GUI provenance', 'cached-formula freshness', 'visual layout/style equivalence', 'every embedded object']}


def wrong_h2_fixture(data):
    """Create an explicitly requested negative-test copy; preserve other ZIP bytes."""
    book = read_workbook(data)
    sheet = next(iter(book['sheets']))
    path = book['sheets'][sheet]['path']
    original = book['members'][path]
    pattern = rb'(<c\b[^>]*\br="H2"[^>]*>)(.*?)(</c>)'
    match = re.search(pattern, original, re.S)
    if not match:
        raise ValueError('fixture H2 not found')
    middle, count = re.subn(rb'<v>.*?</v>', b'<v>868</v>', match.group(2), count=1, flags=re.S)
    if count != 1:
        raise ValueError('fixture H2 numeric cache not found')
    changed = original[:match.start()] + match.group(1) + middle + match.group(3) + original[match.end():]
    result = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as source, zipfile.ZipFile(result, 'w') as target:
        for entry in source.infolist():
            target.writestr(entry, changed if entry.filename == path else source.read(entry.filename))
    return result.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = task_50250(Path(args.input).read_bytes(), Path(args.output).read_bytes())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['artifact_value_pass'] else 1)


if __name__ == '__main__':
    main()
