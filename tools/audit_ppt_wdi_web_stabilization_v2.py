"""Extend the PowerPoint stabilization audit with a raw four-target train run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_stabilization_v1 import (
    require, score, sha, write_new,
)
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-root', type=Path, required=True)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--prior-private-receipt', type=Path, required=True)
    parser.add_argument('--prior-public-receipt', type=Path, required=True)
    parser.add_argument('--controller-v2', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    train, artifact_dir, prior = (path.resolve() for path in
                                   (args.train_root, args.artifact_dir,
                                    args.prior_private_receipt))
    require(all(path.is_relative_to(private) for path in
                (train, artifact_dir, prior)) and
            not args.public_out.exists() and
            not (artifact_dir / 'stabilization-audit-v2.private.json').exists(),
            'private input and fresh public/private receipts required')
    previous_raw = prior.read_bytes()
    previous = json.loads(previous_raw)
    prior_public = json.loads(args.prior_public_receipt.read_bytes())
    require(previous['schema'] ==
            'envloop-ppt-web-stabilization-development-private-v1' and
            prior_public['private_receipt_sha256'] == sha(previous_raw) and
            prior_public['official_final_admitted'] ==
            prior_public['model_calls'] == 0,
            'prior aggregate stabilization evidence changed')
    manifest = json.loads((train / 'manifest.private.json').read_bytes())
    task = manifest['cases'][9]
    source = (train / 'packages/train_policy_development' / task['task_id'] /
              'source.pptx')
    first = artifact_dir / 'train-raw-four-first-baseline.private.pptx'
    second = artifact_dir / 'train-raw-four-second-baseline.private.pptx'
    positive = artifact_dir / 'train-raw-four-positive.private.pptx'
    source_equivalence = semantic_source_equal(source, first)
    second_equivalence = semantic_source_equal(first, second)
    neutral = score(task, first, second)
    outcome = score(task, second, positive)
    require(neutral['status'] == outcome['status'] == 'scored' and
            neutral['score'] == 0 and
            neutral['preservation_pass'] is True and
            sum(row['changed'] for row in neutral['per_target'].values()) == 0
            and outcome['score'] == 1 and
            outcome['preservation_pass'] is True and
            sum(row['changed'] for row in outcome['per_target'].values()) == 4 and
            outcome['unexpected_parts'] == [],
            'raw four-target two-round train GUI control changed')
    require(sha(args.verifier.read_bytes()) ==
            sha(Path(verify.__file__).read_bytes()),
            'provided independent verifier path changed')
    private_receipt = {
        'schema': 'envloop-ppt-web-stabilization-development-private-v2',
        'prior_private_receipt_sha256': sha(previous_raw),
        'train_manifest_sha256': sha((train / 'manifest.private.json').read_bytes()),
        'source_sha256': sha(source.read_bytes()),
        'first_baseline_sha256': sha(first.read_bytes()),
        'second_baseline_sha256': sha(second.read_bytes()),
        'positive_sha256': sha(positive.read_bytes()),
        'source_equivalence': source_equivalence,
        'second_equivalence': second_equivalence,
        'neutral': neutral, 'positive': outcome,
        'controller_v2_sha256': sha(args.controller_v2.read_bytes()),
        'verifier_sha256': sha(args.verifier.read_bytes()),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    receipt_sha = write_new(
        artifact_dir / 'stabilization-audit-v2.private.json',
        private_receipt, 0o600)
    public = {
        'schema': 'envloop-ppt-web-stabilization-development-public-v2',
        'status': 'raw_train_four_target_two_rounds_and_positive_verified',
        'prior_private_receipt_sha256': sha(previous_raw),
        'train_source_to_first_baseline_semantics_preserved': True,
        'train_first_to_second_baseline_semantics_preserved': True,
        'second_baseline_target_changes': 0,
        'second_baseline_preservation_pass': True,
        'four_target_positive_score': 1,
        'four_target_positive_preservation_pass': True,
        'native_chart_and_workbook_preserved_after_freeze': True,
        'controller_v2_sha256': private_receipt['controller_v2_sha256'],
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
