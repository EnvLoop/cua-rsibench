"""Stage four isolated PPT web controls and derive collateral text from OOXML.

The evaluator reads the exact non-target chart-unit shape from the frozen
Office-saved baseline. This avoids a manually transcribed GUI selector. It
does not upload, edit, score, or admit any final identity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal
from tools.materialize_ppt_wdi_normalized_roles_v1 import require, sha, write_new


P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def collateral_spec(pptx: Path) -> dict:
    with zipfile.ZipFile(pptx) as archive:
        slide = ET.fromstring(archive.read('ppt/slides/slide3.xml'))
    matches = []
    for shape in slide.iter(P + 'sp'):
        name = shape.find(P + 'nvSpPr/' + P + 'cNvPr')
        if name is not None and name.get('name') == 'chart_unit':
            matches.append(''.join((node.text or '')
                                   for node in shape.iter(A + 't')))
    require(len(matches) == 1 and matches[0] and
            '(unapproved)' not in matches[0],
            'one original non-target chart unit required')
    return {'key': 'collateral', 'slide': 3,
            'draft': matches[0],
            'corrupt': matches[0] + ' (unapproved)'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--normalized-baseline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    manifest_path, out = args.manifest.resolve(), args.out.resolve()
    require(manifest_path.is_relative_to(private) and
            out.is_relative_to(private) and not out.exists(),
            'private manifest and new work/ receipt required')
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest['schema'] ==
            'envloop-ppt-wdi-web-final-gui-staging-private-v2' and
            manifest['case_count'] == 100 and 0 <= args.index < 100,
            '100-case baseline staging manifest changed')
    case = manifest['cases'][args.index]
    require(case['index'] == args.index and len(case['targets']) == 4,
            'case index or four target fields changed')
    source = Path(case['source_path'])
    source_raw = source.read_bytes()
    require(sha(source_raw) == case['source_sha256'] and
            Path(case['copies']['baseline']).read_bytes() == source_raw,
            'original local source baseline changed')
    task = json.loads(source.with_name('task.private.json').read_bytes())
    require(task['task_id'] == case['task_id'],
            'private task package differs from staging case')
    verify.freeze(source, task)
    baseline_raw = args.normalized_baseline.read_bytes()
    require(sha(baseline_raw) != case['source_sha256'],
            'trusted Office baseline save was not observed')
    verify.freeze(args.normalized_baseline, task,
                  office_web_normalized=True)
    source_equivalence = semantic_source_equal(source, args.normalized_baseline)
    collateral = collateral_spec(args.normalized_baseline)
    case_dir = manifest_path.parent / f'case-{args.index:03d}'
    roles = {}
    for role in ('positive', 'near_miss', 'fresh_reset', 'collateral'):
        path = (Path(case['copies'][role]) if role != 'collateral' else
                case_dir / f'EL-PPT-Final-{args.index + 1:03d}-collateral.pptx')
        target = path.resolve()
        require(target.is_relative_to(case_dir) and not target.exists(),
                'normalized role copy already exists or left private staging')
        write_new(target, baseline_raw)
        roles[role] = {'path': str(target),
                       'sha256': sha(target.read_bytes())}
    require(len({row['sha256'] for row in roles.values()}) == 1 and
            next(iter(roles.values()))['sha256'] == sha(baseline_raw),
            'role copies differ from frozen Office baseline')
    receipt = {'schema': 'envloop-ppt-wdi-normalized-roles-private-v2',
               'index': args.index, 'task_id': case['task_id'],
               'source_sha256': case['source_sha256'],
               'normalized_baseline_sha256': sha(baseline_raw),
               'source_equivalence': source_equivalence,
               'collateral': collateral,
               'roles': roles,
               'model_calls': 0, 'official_final_admitted': 0}
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    write_new(out, raw)
    print(json.dumps({'status': 'four_exact_normalized_roles_staged',
                      'case_index': args.index,
                      'copy_count': len(roles),
                      'baseline_sha256': sha(baseline_raw),
                      'private_receipt_sha256': sha(raw),
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
