"""Audit two-download PowerPoint web GUI controls on a training source."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_stabilization_v1 import (
    require, score, sha, write_new,
)
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


ROLES = ('neutral', 'positive', 'near_miss', 'fresh_reset', 'collateral')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-root', type=Path, required=True)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--controller-v4', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    train, artifacts = args.train_root.resolve(), args.artifact_dir.resolve()
    require(train.is_relative_to(private) and artifacts.is_relative_to(private)
            and not args.public_out.exists() and
            not (artifacts / 'v4-train-audit.private.json').exists(),
            'private inputs and fresh receipts required')
    manifest = json.loads((train / 'manifest.private.json').read_bytes())
    task = manifest['cases'][9]
    source = train / 'gui-controller/v6-normalized-baseline.pptx'
    neutral = artifacts / 'neutral-2.private.pptx'
    source_equivalence = semantic_source_equal(source, neutral)
    oracle = verify.freeze(neutral, task, office_web_normalized=True)
    input_names = {
        'positive': 'EL-PPT-Train-V4-Final-positive.pptx',
        'near_miss': 'EL-PPT-Train-V4-Final-near-miss.pptx',
        'fresh_reset': 'EL-PPT-Train-V4-Final-reset.pptx',
        'collateral': 'EL-PPT-Train-V4-Final-collateral.pptx',
    }
    for name in input_names.values():
        require((train / 'gui-controller' / name).read_bytes() ==
                neutral.read_bytes(),
                'role did not begin from exact frozen Office baseline')
    outcomes = {}
    for role in ROLES:
        first, second = (artifacts / f'{role}-{index}.private.pptx'
                         for index in (1, 2))
        require(first.read_bytes() == second.read_bytes(),
                'two independent cloud downloads disagree')
        outcomes[role] = score(task, source if role == 'neutral' else neutral,
                               second)
        require(outcomes[role]['status'] == 'scored',
                'independent saved-PPTX scorer could not read role')
    expectations = {
        'neutral': (0, 0, True),
        'positive': (1, 4, True),
        'near_miss': (0, 3, True),
        'fresh_reset': (0, 0, True),
        'collateral': (0, 0, False),
    }
    for role, (score_value, changes, preservation) in expectations.items():
        result = outcomes[role]
        require(result['score'] == score_value and
                sum(row['changed'] for row in
                    result['per_target'].values()) == changes and
                result['preservation_pass'] is preservation,
                role + ' training GUI control no longer discriminates')
    require(outcomes['positive']['unexpected_parts'] == [] and
            'ppt/slides/slide3.xml' in
            outcomes['collateral']['unexpected_parts'],
            'positive no-regression or collateral rejection changed')
    files = {path.name: sha(path.read_bytes())
             for path in sorted(artifacts.glob('*.private.pptx'))}
    private_receipt = {
        'schema': 'envloop-ppt-web-v4-training-controls-private-v1',
        'train_manifest_sha256': sha((train / 'manifest.private.json').read_bytes()),
        'source_sha256': sha(source.read_bytes()),
        'normalized_baseline_sha256': sha(neutral.read_bytes()),
        'source_equivalence': source_equivalence,
        'outcomes': outcomes,
        'saved_artifact_sha256': files,
        'controller_v4_sha256': sha(args.controller_v4.read_bytes()),
        'verifier_sha256': sha(args.verifier.read_bytes()),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    receipt_sha = write_new(artifacts / 'v4-train-audit.private.json',
                            private_receipt, 0o600)
    public = {
        'schema': 'envloop-ppt-web-v4-training-controls-public-v1',
        'status': 'training_source_five_gui_roles_saved_pptx_verified',
        'two_downloads_byte_identical_per_role': 5,
        'source_to_office_baseline_semantics_preserved': True,
        'target_changes_by_role': {role: changes for role,
                                   (_, changes, _) in expectations.items()},
        'score_by_role': {role: score_value for role,
                          (score_value, _, _) in expectations.items()},
        'preservation_by_role': {role: preservation for role,
                                 (_, _, preservation) in expectations.items()},
        'independent_saved_pptx_verifier': True,
        'controller_v4_sha256': private_receipt['controller_v4_sha256'],
        'verifier_sha256': private_receipt['verifier_sha256'],
        'private_receipt_sha256': receipt_sha,
        'model_calls': 0, 'official_final_admitted': 0,
    }
    public_sha = write_new(args.public_out, public, 0o644)
    print(json.dumps({'status': public['status'],
                      'public_receipt_sha256': public_sha,
                      'private_receipt_sha256': receipt_sha,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
