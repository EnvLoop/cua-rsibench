"""Audit one original-software PowerPoint V5 final-candidate GUI control.

The receipt is evaluator-private. A passing control is not an official final
admission until shared six-cell rights, runtime and model protocols are frozen.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from tools.audit_ppt_wdi_web_stabilization_v1 import require, score, sha, write_new
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal
from tools.materialize_ppt_wdi_normalized_roles_v2 import collateral_spec


DOWNLOAD_PAIRS = ('phase1-positive', 'phase1-neutral',
                  'phase2-positive', 'phase2-neutral',
                  'role-positive', 'role-near-miss',
                  'role-fresh-reset', 'role-collateral')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--cloud-witness', type=Path, required=True)
    parser.add_argument('--controller-v5', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    root, staging = args.private_root.resolve(), args.staging.resolve()
    out = args.out.resolve()
    require(root.is_relative_to(private) and staging.is_relative_to(private)
            and out.is_relative_to(private) and not out.exists() and
            0 <= args.index < 100,
            'private v12 inputs, index and fresh receipt required')
    plan_raw = (root / 'candidate-plan.private.json').read_bytes()
    plan = json.loads(plan_raw)
    manifest_raw = (staging / 'manifest.private.json').read_bytes()
    manifest = json.loads(manifest_raw)
    require(plan['revision'] == 'private_wdi_seven_reserves_and_web_chart_v9'
            and manifest['plan_sha256'] == sha(plan_raw)
            and manifest['case_count'] == 100,
            'frozen six-reserve staging plan changed')
    row = plan['sets']['final_candidate'][args.index]
    case = manifest['cases'][args.index]
    directory = staging / f'case-{args.index:03d}'
    require(case['task_id'] == row['task_id'] and
            case['source_group'] == row['source_group'] and
            Path(case['source_path']).resolve() ==
            (root / 'packages/final_candidate' / row['task_id'] /
             'source.pptx').resolve(),
            'candidate identity/source binding changed')
    source = Path(case['source_path'])
    require(sha(source.read_bytes()) == case['source_sha256'] and
            json.loads(source.with_name('task.private.json').read_bytes()) == row,
            'original source or task changed')
    witness_raw = args.cloud_witness.read_bytes()
    witness = json.loads(witness_raw)
    cloud = witness['cloud_item_document_ids']
    require(witness['schema'] == 'envloop-ppt-v5-cloud-witness-private-v1'
            and witness['index'] == args.index and
            set(cloud) == {'raw', 'second_normalization', 'positive',
                           'near_miss', 'fresh_reset', 'collateral'} and
            len(set(cloud.values())) == len(cloud) and
            all(re.fullmatch(r'[0-9A-F]{8}(?:-[0-9A-F]{4}){3}-[0-9A-F]{12}',
                             value) for value in cloud.values()) and
            witness['gui_controller'] == 'ppt_wdi_web_gui_controller_v5.js',
            'six distinct observed cloud items required')

    files = {}
    upload_prefix = f'EL-PPT-V13-Final-{args.index + 1:03d}'
    for role in DOWNLOAD_PAIRS:
        first, second = (directory / f'{role}-{i}.private.pptx'
                         for i in (1, 2))
        require(first.read_bytes() == second.read_bytes(),
                f'{role}: successive read-only cloud downloads differ')
        files[role] = second
    n1, n2 = files['phase1-neutral'], files['phase2-neutral']
    require((directory / f'{upload_prefix}-stabilize-2.pptx')
            .read_bytes() == n1.read_bytes() and
            (directory / 'normalized-baseline.private.pptx')
            .read_bytes() == n2.read_bytes(),
            'second neutral preparation did not start from first baseline')
    roles = json.loads((directory / 'normalized-roles.private.json').read_bytes())
    require(roles['schema'] == 'envloop-ppt-wdi-normalized-roles-private-v2'
            and roles['index'] == args.index and
            roles['normalized_baseline_sha256'] == sha(n2.read_bytes()) and
            roles['collateral'] == collateral_spec(n2) and
            all(roles['roles'][role]['sha256'] == sha(n2.read_bytes())
                for role in ('positive', 'near_miss', 'fresh_reset',
                             'collateral')),
            'four source-derived role copies differ from frozen baseline')
    for role in ('positive', 'near-miss', 'fresh-reset', 'collateral'):
        require((directory / f'{upload_prefix}-{role}.pptx')
                .read_bytes() == n2.read_bytes(),
                f'{role}: uploaded source copy is not the frozen baseline')

    source_equivalence = semantic_source_equal(source, n1)
    second_equivalence = semantic_source_equal(source, n2)
    checks = {
        'phase1_positive': score(row, n1, files['phase1-positive']),
        'neutral_stability': score(row, n1, n2),
        'phase2_positive': score(row, n2, files['phase2-positive']),
        'fresh_positive': score(row, n2, files['role-positive']),
        'near_miss': score(row, n2, files['role-near-miss']),
        'fresh_reset': score(row, n2, files['role-fresh-reset']),
        'collateral': score(row, n2, files['role-collateral']),
    }
    expected = {
        'phase1_positive': (1, 4, True),
        'neutral_stability': (0, 0, True),
        'phase2_positive': (1, 4, True),
        'fresh_positive': (1, 4, True),
        'near_miss': (0, 3, True),
        'fresh_reset': (0, 0, True),
        'collateral': (0, 0, False),
    }
    for name, (value, changes, preservation) in expected.items():
        result = checks[name]
        require(result['status'] == 'scored' and result['score'] == value and
                sum(item['changed'] for item in
                    result['per_target'].values()) == changes and
                result['preservation_pass'] is preservation and
                (result['unexpected_parts'] == [] if preservation else
                 result['unexpected_parts'] == ['ppt/slides/slide3.xml']),
                f'{name}: independent saved-state control failed')

    receipt = {
        'schema': 'envloop-ppt-v5-final-gui-control-private-v2',
        'index': args.index, 'task_id': row['task_id'],
        'plan_sha256': sha(plan_raw),
        'staging_manifest_sha256': sha(manifest_raw),
        'source_sha256': sha(source.read_bytes()),
        'source_equivalence': source_equivalence,
        'second_source_equivalence': second_equivalence,
        'frozen_baseline_sha256': sha(n2.read_bytes()),
        'download_sha256': {role: sha(path.read_bytes())
                            for role, path in files.items()},
        'cloud_witness_sha256': sha(witness_raw),
        'source_derived_collateral_spec_sha256': sha(
            json.dumps(roles['collateral'], sort_keys=True).encode()),
        'controller_v5_sha256': sha(args.controller_v5.read_bytes()),
        'verifier_sha256': sha(args.verifier.read_bytes()),
        'scores': {role: checks[role]['score'] for role in checks},
        'per_id_gui_controls_passed': True,
        'model_calls': 0,
        'official_final_admitted': 0,
    }
    receipt_sha = write_new(out, receipt, 0o600)
    print(json.dumps({'status': 'final_candidate_gui_controls_passed_not_official',
                      'private_receipt_sha256': receipt_sha,
                      'per_id_gui_controls_passed': True,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
