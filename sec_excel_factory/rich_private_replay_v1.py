"""Portable, byte-preserving replay of the current private rich SEC140 corpus.

Private outputs preserve original actor/reference/source bytes and independent
graph code. No proprietary artifact runtime is used and no native qualification
is inherited. Public output contains aggregate counts and integrity hashes only.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import argparse
import importlib.util
import json
import os
import tempfile

from tools import office_owned_folder_runtime_v2 as runtime
from tools.office_current_package_v5 import Package

CURRENT_AUDITOR_SHA = '7585dd5af0af9f7ce63671efc436dcf9f340d4622afb155d830d0d1bf025127d'
CURRENT_AUDIT_SHA = '85e89610cdeeed7cc38ab6204d505a19513c4b304e9f570dbefe0781a99a0845'
CURRENT_RESERVATIONS_SHA = '3459c1e2fbc4a02dbece31379849c28d52d12bf17b3d188a709590c1ee7df937'
COUNTS = {'train': 20, 'selection': 20, 'final': 100}
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def _read(path):
    path = Path(path)
    runtime.require(path.is_file() and not path.is_symlink() and path.stat().st_size < 50_000_000,
                    'Original rich source regular file required')
    return path.read_bytes()


def _archive(root):
    source_root = root.parents[1]
    buffer = BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        def add(name, raw):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, raw)
        for path in sorted(root.rglob('verify*.py')):
            add('work/private-excel/' + str(path.relative_to(root)), _read(path))
        for name in ('verify_ooxml.py', 'extract_sec.py'):
            add('sec_excel_factory/' + name, _read(source_root / 'sec_excel_factory' / name))
    return buffer.getvalue()


def _metadata(root):
    for name, expected in (('audit_integrated_private_split.py', CURRENT_AUDITOR_SHA),
            ('integrated-offline-audit.json', CURRENT_AUDIT_SHA),
            ('private-split-reservations.json', CURRENT_RESERVATIONS_SHA)):
        runtime.require(runtime.sha(_read(root / name)) == expected,
                        'Current rich SEC source epoch changed; review required')
    spec = importlib.util.spec_from_file_location('rich_sec_metadata', root / 'audit_integrated_private_split.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    audit = json.loads(_read(root / 'integrated-offline-audit.json'))
    rows, stage_refs = [], []
    fact_total = 0
    for manifest, stage_audit, verifier, workbooks, split, facts, _ in module.STAGES:
        cases = json.loads(_read(root / manifest)); stage = json.loads(_read(root / stage_audit))
        fact_total += facts
        count = len(cases)
        targets = stage.get('formula_targets_per_workbook')
        if targets is None:
            runtime.require(stage['checked_formula_targets_total'] % count == 0, 'Rich stage target count invalid')
            targets = stage['checked_formula_targets_total'] // count
        faults = stage.get('unmarked_faults_individually_detected',
            stage.get('unmarked_faults_individually_rejected_in_saved_ooxml',
            stage.get('isolated_saved_OOXML_fault_rejections')))
        runtime.require(stage['candidate_workbook_pairs'] == count and faults == count * 9 and
            stage['counterfactual_profiles_per_case'] == 2 and
            stage.get('positive_reference_passes', stage.get('positive_references_passed')) == count and
            stage.get('unrepaired_seed_rejections', stage.get('unrepaired_seeds_rejected')) == count,
            'Original rich stage control receipt changed')
        stage_refs.append((stage_audit, runtime.sha(_read(root / stage_audit))))
        for case in cases:
            private_oracle = json.loads(_read(root / workbooks / case['case_id'] / 'private-oracle.json'))
            case_targets = len(private_oracle['targets'])
            runtime.require(case_targets > 0 and private_oracle['case_id'] == case['case_id'],
                            'Rich per-case formula target identity changed')
            rows.append({'case': case, 'split': split, 'verifier': verifier,
                         'workbook_root': root / workbooks / case['case_id'], 'targets': case_targets,
                         'stage_audit': root / stage_audit})
    runtime.require(runtime.sha(json.dumps(stage_refs, separators=(',', ':')).encode()) ==
        audit['stage_audit_commitment_sha256'], 'Original rich stage audit commitments changed')
    runtime.require(fact_total == 1997 and sum(row['targets'] for row in rows) == 9985,
                    'Current rich original fact or target totals changed')
    runtime.require(Counter(r['split'] for r in rows) == Counter(COUNTS) and
        len({r['case']['case_id'] for r in rows}) == 140 and
        len({r['case']['filing_accession'] for r in rows}) == 140,
        'Exact current rich SEC140 source identities required')
    issuers, graphs = defaultdict(set), defaultdict(set)
    for row in rows:
        issuers[row['case']['cik']].add(row['split']); graphs[row['split']].add(row['case']['template_family'])
    runtime.require(len(issuers) == 33 and all(len(s) == 1 for s in issuers.values()) and
        max(Counter(row['case']['cik'] for row in rows).values()) <= 5 and
        sum(len(s) for s in graphs.values()) == 16 and len(graphs['final']) == 13 and
        not any(graphs[a] & graphs[b] for a, b in (('train','selection'),('train','final'),('selection','final'))),
        'Rich source or semantic graph split isolation changed')
    slots = json.loads(_read(root / 'private-split-reservations.json'))['slots']
    by_id = {r['case']['case_id']: r for r in rows}
    ordered = []
    for slot in slots:
        row = by_id[slot['offline_case_id']]; case = row['case']
        runtime.require(slot['status'] == 'offline_calibration_candidate' and
            (slot['split'], slot['issuer_cik'], slot['original_filing_accession'], slot['semantic_template_reservation']) ==
            (row['split'], case['cik'], case['filing_accession'], case['template_family']),
            'Rich original slot binding changed')
        ordered.append(row)
    runtime.require(len(ordered) == 140 and len({r['case']['case_id'] for r in ordered}) == 140,
                    'Rich slot order incomplete or duplicate')
    return ordered, audit


def _sheet_path(archive, sheet):
    book = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    mapping = {element.attrib['Id']: element.attrib['Target'] for element in rels}
    match = next(element for element in book.findall('m:sheets/m:sheet', NS) if element.attrib['name'] == sheet)
    target = mapping[match.attrib['{' + NS['r'] + '}id']]
    return target.lstrip('/') if target.startswith('/') else 'xl/' + target


def isolated_fault(reference, actor, fault, output):
    """Replace one saved formula/value while retaining every other ZIP member."""
    sheet, address = fault.split('!', 1)
    with ZipFile(reference) as positive, ZipFile(actor) as broken:
        member = _sheet_path(positive, sheet); other = _sheet_path(broken, sheet)
        root = ET.fromstring(positive.read(member)); donor_root = ET.fromstring(broken.read(other))
        target = root.find(f'.//m:c[@r="{address}"]', NS)
        donor = donor_root.find(f'.//m:c[@r="{address}"]', NS)
        runtime.require(target is not None and donor is not None and donor.attrib.get('t') != 's',
                        'Rich isolated fault cell missing or shared-string unsupported')
        for child in list(target): target.remove(child)
        for child in donor: target.append(deepcopy(child))
        if 't' in donor.attrib: target.attrib['t'] = donor.attrib['t']
        else: target.attrib.pop('t', None)
        with ZipFile(output, 'w', ZIP_DEFLATED) as out:
            for item in positive.infolist():
                out.writestr(item, ET.tostring(root, encoding='utf-8') if item.filename == member else positive.read(item.filename))
    Path(output).chmod(0o600)


def prepare(*, private_root, output_root, case_ordinals=None):
    root, out = Path(private_root).resolve(), Path(output_root).resolve()
    runtime.require(not out.exists() and not out.is_symlink(), 'Fresh rich SEC replay output required')
    rows, old_audit = _metadata(root)
    ordinals = list(range(140)) if case_ordinals is None else list(case_ordinals)
    runtime.require(ordinals and len(set(ordinals)) == len(ordinals) and
        all(type(i) is int and 0 <= i < 140 for i in ordinals), 'Rich test subset ordinal invalid')
    out.mkdir(parents=True, mode=0o700)
    source = _archive(root); runtime.write_new(out / 'original-graph-source.private.zip', source)
    metadata, control_rows = [], []
    for ordinal in ordinals:
        row = rows[ordinal]; case = dict(row['case']); split = 'final_candidate' if row['split'] == 'final' else row['split']
        task_id = f'sec-rich-{ordinal + 1:04d}'
        package = out / 'excel-web' / split / task_id; package.mkdir(parents=True, mode=0o700)
        for source_name, target_name in (('actor.xlsx','source.xlsx'),('reference.xlsx','reference.private.xlsx'),
                ('private-oracle.json','private-oracle.private.json'),('task.md','task.md')):
            runtime.write_new(package / target_name, _read(row['workbook_root'] / source_name))
        excerpt = _read(case['source_excerpt_path'])
        runtime.require(runtime.sha(excerpt) == case['source_excerpt_sha256'], 'Original rich excerpt changed')
        runtime.write_new(package / 'source-excerpt.private.json', excerpt)
        case['source_excerpt_path'] = 'source-excerpt.private.json'
        runtime.write_new(package / 'case-manifest.private.json', runtime.canonical([case]))
        instruction = (package / 'task.md').read_text()
        runtime.write_new(package / 'task.private.json', runtime.canonical({'task_id':task_id,'split':split,'actor_task':instruction}))
        os.link(out / 'original-graph-source.private.zip', package / 'original-graph-source.private.zip')
        oracle = {'schema':'office-rich-sec-oracle-private-v1','case_id':case['case_id'],
                  'verifier':'work/private-excel/' + row['verifier'],'checked_targets':row['targets'],
                  'counterfactual_profiles':2,'original_integrated_audit_sha256':CURRENT_AUDIT_SHA,
                  'original_stage_audit_sha256':runtime.sha(_read(row['stage_audit']))}
        runtime.write_new(package / 'rich-oracle.private.json', runtime.canonical(oracle))
        runtime.descriptor(cell_id='excel-web',split=split,task_id=task_id,instruction=instruction,
            baseline=package/'source.xlsx',task_spec=package/'task.private.json',out=package/'descriptor-initial.private.json',
            extra_refs={'case_manifest':package/'case-manifest.private.json','rich_oracle_source':package/'original-graph-source.private.zip',
                'rich_oracle_manifest':package/'rich-oracle.private.json','source_excerpt':package/'source-excerpt.private.json',
                'private_oracle':package/'private-oracle.private.json'},case_id=case['case_id'])
        value = json.loads(runtime.private(package/'descriptor-initial.private.json')); value['rich_sec_graph'] = True
        runtime.write_new(package/'package.private.json', runtime.canonical(value))
        checked = Package(package/'package.private.json', package_root=package)
        faults = json.loads(runtime.private(package/'private-oracle.private.json'))['faulted']
        runtime.require(len(faults) == 9 and len(set(faults)) == 9, 'Nine original isolated faults required')
        directory = package/'offline-controls.private'; directory.mkdir(mode=0o700)
        candidates = [package/'source.xlsx', package/'reference.private.xlsx']
        for index, fault in enumerate(faults):
            candidate = directory/f'isolated-{index:02d}.xlsx'
            isolated_fault(candidates[1], candidates[0], fault, candidate); candidates.append(candidate)
        results = checked.score_many(candidates)
        runtime.require([r['score'] for r in results] == [0.0,1.0] + [0.0]*9,
                        'Original rich positive, unrepaired or isolated fault controls failed')
        controls = {'ordinal':ordinal,'task_id':task_id,'package_sha256':checked.binding_sha256,
            'baseline_score':0,'positive_score':1,'isolated_fault_rejections':9,
            'checked_targets':row['targets'],'counterfactual_profiles':2,
            'actor_original_sha256':runtime.sha(_read(row['workbook_root']/'actor.xlsx')),
            'reference_original_sha256':runtime.sha(_read(row['workbook_root']/'reference.xlsx')),
            'source_original_sha256':case['source_excerpt_sha256'],
            'scored_artifact_refs':[{'path':str(path.relative_to(package)),
                                    'sha256':runtime.sha(runtime.private(path))} for path in candidates],
            'raw_strict_controls':results}
        runtime.write_new(package/'offline-controls.private.json',runtime.canonical(controls)); control_rows.append(controls)
        metadata.append({'cell_id':'excel-web','split':split,'task_id':task_id,
            'package_sha256':checked.binding_sha256,'package_root':str(package),
            'descriptor':str(package/'package.private.json'),'package_adapter':'tools.office_current_package_v5.Package'})
    full = case_ordinals is None
    receipt = {'schema':'office-rich-sec-portable-replay-v1','scope':'current-rich140' if full else 'explicit-development-subset',
        'counts':dict(Counter(r['split'] for r in metadata)),'packages':len(metadata),'source_bytes_preserved':True,
        'original_graph_source_sha256':runtime.sha(source),'original_integrated_audit_sha256':CURRENT_AUDIT_SHA,
        'execution_source_sha256s':{name:runtime.sha(_read(Path(__file__).resolve().parents[1]/name))
            for name in ('sec_excel_factory/rich_private_replay_v1.py','tools/office_current_package_v5.py')},
        'original_issuer_families':33 if full else None,'original_filing_count':140 if full else None,
        'original_numeric_fact_count':1997 if full else None,
        'original_graph_count':16 if full else None,'original_final_graph_count':13 if full else None,
        'checked_formula_targets':sum(r['checked_targets'] for r in control_rows),
        'isolated_fault_rejections':sum(r['isolated_fault_rejections'] for r in control_rows),
        'positive_reference_passes':len(control_rows),'unrepaired_seed_rejections':len(control_rows),
        'source_and_scenario_counterfactual_profiles_per_case':2,
        'native_lifecycle_qualified':False,'structurally_qualified_tasks':0,'gui_admitted_final_count':0,
        'model_calls':0,'native_calls':0,'official_final_credit':0}
    if full:
        runtime.require(receipt['checked_formula_targets'] == 9985 and receipt['isolated_fault_rejections'] == 1260,
                        'Rich full replay original control totals changed')
    runtime.write_new(out/'execution-metadata-index.private.json',runtime.canonical(metadata))
    runtime.write_new(out/'portable-rich-replay-receipt.private.json',runtime.canonical(receipt))
    return receipt


def relocate_metadata(*, source_index, package_root, output_index):
    """Write a fresh host-local index after private package transport.

    Frozen descriptor/source bytes are not edited, and existing qualifications
    do not transfer to the new index or host.
    """
    rows = json.loads(runtime.private(source_index)); root = Path(package_root).resolve()
    runtime.require(type(rows) is list and len(rows) == 140 and
        Counter(row['split'] for row in rows) == Counter({'train':20,'selection':20,'final_candidate':100}),
        'Exact current rich140 index required for relocation')
    output = []
    for row in rows:
        runtime.require(row.get('cell_id') == 'excel-web' and
            row.get('package_adapter') == 'tools.office_current_package_v5.Package' and
            row['task_id'].startswith('sec-rich-'), 'Rich portable index identity changed')
        package_root = root/'excel-web'/row['split']/row['task_id']
        descriptor = package_root/'package.private.json'
        package = Package(descriptor,package_root=package_root)
        runtime.require(package.binding_sha256 == row['package_sha256'] and
            package.actor.task_id == row['task_id'] and package.actor.split == row['split'],
            'Transported rich frozen package changed')
        output.append(dict(row,package_root=str(package_root),descriptor=str(descriptor)))
    runtime.write_new(output_index,runtime.canonical(output))
    return {'schema':'office-rich-sec-portable-relocation-v1','packages':140,
            'descriptor_bytes_unchanged':True,'native_lifecycle_qualified':False,'official_final_credit':0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root'); parser.add_argument('--output-root')
    parser.add_argument('--relocate-index'); parser.add_argument('--package-root'); parser.add_argument('--output-index')
    parser.add_argument('--development-ordinals', help='Comma-separated explicit source-only test ordinals')
    args = parser.parse_args()
    if args.relocate_index:
        print(json.dumps(relocate_metadata(source_index=args.relocate_index,package_root=args.package_root,
            output_index=args.output_index),sort_keys=True)); return
    indices = [int(i) for i in args.development_ordinals.split(',')] if args.development_ordinals else None
    print(json.dumps(prepare(private_root=args.private_root, output_root=args.output_root, case_ordinals=indices), sort_keys=True))


if __name__ == '__main__':
    main()
