"""Audit persisted-positive PowerPoint-web normalization on a training source.

The downloaded PPTX bytes, not the editor UI, are the scoring input. This
development-only audit cannot grant any final-task admission or model credit.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.audit_ppt_wdi_web_stabilization_v1 import require, score, sha, write_new
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


PAIRS = ('persisted-positive', 'restored-neutral', 'second-positive',
         'second-neutral', 'fresh-positive', 'near-miss', 'fresh-reset',
         'collateral')


def compact(result: dict) -> dict:
    return {'score': result['score'],
            'target_changes': sum(v['changed'] for v in
                                  result['per_target'].values()),
            'preservation_pass': result['preservation_pass'],
            'unexpected_parts': result['unexpected_parts']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-root', type=Path, required=True)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--controller-v5', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    train, artifacts = args.train_root.resolve(), args.artifact_dir.resolve()
    require(train.is_relative_to(private) and artifacts.is_relative_to(private)
            and not args.public_out.exists() and
            not (artifacts / 'v5-train-audit.private.json').exists(),
            'private inputs and fresh receipts required')
    manifest = json.loads((train / 'manifest.private.json').read_bytes())
    task = manifest['cases'][9]
    package = train / 'packages/train_policy_development' / task['task_id']
    source = package / 'source.pptx'
    require((artifacts / 'EL-PPT-Train-V5-Raw-Round2.pptx').read_bytes() ==
            source.read_bytes(), 'training raw source differs')

    files = {}
    for role in PAIRS:
        first, second = (artifacts / f'{role}-{i}.private.pptx'
                         for i in (1, 2))
        require(first.read_bytes() == second.read_bytes(),
                f'{role}: two read-only downloads disagree')
        files[role] = second
    n1, n2 = files['restored-neutral'], files['second-neutral']
    require((artifacts / 'EL-PPT-Train-V5-Normalized-Round3.pptx')
            .read_bytes() == n1.read_bytes(),
            'second normalization did not start from the first saved baseline')
    for role in ('FreshPositive', 'NearMiss', 'FreshReset', 'Collateral'):
        require((artifacts / f'EL-PPT-Train-V5-{role}.pptx').read_bytes()
                == n2.read_bytes(),
                'role copy did not start from the second saved baseline')

    source_equivalence = semantic_source_equal(source, n1)
    second_source_equivalence = semantic_source_equal(source, n2)
    checks = {
        'first_positive': score(task, n1, files['persisted-positive']),
        'second_positive': score(task, n2, files['second-positive']),
        'neutral_stability': score(task, n1, n2),
        'fresh_positive': score(task, n2, files['fresh-positive']),
        'near_miss': score(task, n2, files['near-miss']),
        'fresh_reset': score(task, n2, files['fresh-reset']),
        'collateral': score(task, n2, files['collateral']),
    }
    expected = {
        'first_positive': (1, 4, True),
        'second_positive': (1, 4, True),
        'neutral_stability': (0, 0, True),
        'fresh_positive': (1, 4, True),
        'near_miss': (0, 3, True),
        'fresh_reset': (0, 0, True),
        'collateral': (0, 0, False),
    }
    for name, (value, changes, preservation) in expected.items():
        result = checks[name]
        require(result['status'] == 'scored' and result['score'] == value
                and compact(result)['target_changes'] == changes
                and result['preservation_pass'] is preservation,
                f'{name}: independent saved-state control failed')
    require(all(checks[name]['unexpected_parts'] == []
                for name in expected if name != 'collateral')
            and checks['collateral']['unexpected_parts'] ==
            ['ppt/slides/slide3.xml'],
            'non-target chart-unit rejection or no-regression changed')

    receipt = {
        'schema': 'envloop-ppt-web-v5-train-persisted-positive-private-v1',
        'train_manifest_sha256': sha((train / 'manifest.private.json').read_bytes()),
        'source_sha256': sha(source.read_bytes()),
        'first_baseline_sha256': sha(n1.read_bytes()),
        'second_baseline_sha256': sha(n2.read_bytes()),
        'source_equivalence': source_equivalence,
        'second_source_equivalence': second_source_equivalence,
        'checks': {k: compact(v) for k, v in checks.items()},
        'saved_artifact_sha256': {
            p.name: sha(p.read_bytes())
            for p in sorted(artifacts.glob('*.private.pptx'))},
        'controller_v5_sha256': sha(args.controller_v5.read_bytes()),
        'verifier_sha256': sha(args.verifier.read_bytes()),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    receipt_sha = write_new(artifacts / 'v5-train-audit.private.json',
                            receipt, 0o600)
    public = {
        'schema': 'envloop-ppt-web-v5-train-persisted-positive-public-v1',
        'status': 'training_source_two_phase_gui_controls_verified',
        'two_downloads_byte_identical_per_phase_or_role': len(PAIRS),
        'two_successive_neutral_baselines_source_semantics_preserved': True,
        'score_by_control': {k: v[0] for k, v in expected.items()},
        'target_changes_by_control': {k: v[1] for k, v in expected.items()},
        'preservation_by_control': {k: v[2] for k, v in expected.items()},
        'controller_v5_sha256': receipt['controller_v5_sha256'],
        'verifier_sha256': receipt['verifier_sha256'],
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
