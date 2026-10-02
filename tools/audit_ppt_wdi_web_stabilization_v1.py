"""Audit train-only and quarantined PowerPoint web save stabilization.

The public receipt contains aggregate outcomes and hashes only. Every saved
PPTX, task identity, cloud locator and failed development artifact stays under
the ignored evaluator-private work tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


def require(value: bool, message: str) -> None:
    if not value:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, value: dict, mode: int) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def score(task: dict, baseline: Path, attempt: Path) -> dict:
    return verify.verify(baseline, attempt,
                         verify.freeze(baseline, task,
                                       office_web_normalized=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', type=Path, required=True)
    parser.add_argument('--train-root', type=Path, required=True)
    parser.add_argument('--v8-staging', type=Path, required=True)
    parser.add_argument('--v9-staging', type=Path, required=True)
    parser.add_argument('--controller-v1', type=Path, required=True)
    parser.add_argument('--controller-v2', type=Path, required=True)
    parser.add_argument('--open-helper', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    artifacts, train, v8, v9 = (path.resolve() for path in
                                (args.artifact_dir, args.train_root,
                                 args.v8_staging, args.v9_staging))
    require(all(path.is_relative_to(private) for path in
                (artifacts, train, v8, v9)) and
            not args.public_out.exists() and
            not (artifacts / 'stabilization-audit.private.json').exists(),
            'private inputs and fresh receipts required')
    rows = json.loads((train / 'manifest.private.json').read_bytes())['cases']
    one, four = rows[0], rows[9]
    source_one = (train / 'packages/train_policy_development' /
                  one['task_id'] / 'source.pptx')
    first = artifacts / 'train-single-first-baseline.private.pptx'
    second = artifacts / 'train-single-second-baseline.private.pptx'
    partial = artifacts / 'train-single-partial-positive.private.pptx'
    positive = artifacts / 'train-four-positive.private.pptx'
    neutral_four = artifacts / 'train-four-neutral.private.pptx'
    source_equivalence = semantic_source_equal(source_one, first)
    stage_equivalence = semantic_source_equal(first, second)
    partial_score, positive_score = (score(one, second, path)
                                     for path in (partial, positive))
    require(partial_score['status'] == positive_score['status'] == 'scored' and
            partial_score['score'] == 0 and
            partial_score['preservation_pass'] is True and
            sum(row['changed'] for row in partial_score['per_target'].values()) == 1
            and positive_score['score'] == 1 and
            positive_score['preservation_pass'] is True and
            sum(row['changed'] for row in positive_score['per_target'].values()) == 4,
            'train single/complete controls changed')
    train_four_baseline = train / 'gui-controller/v6-normalized-baseline.pptx'
    neutral = score(four, train_four_baseline, neutral_four)
    require(neutral['status'] == 'scored' and neutral['score'] == 0 and
            neutral['preservation_pass'] is True and
            sum(row['changed'] for row in neutral['per_target'].values()) == 0,
            'four-target train GUI restoration failed')
    v8_case = json.loads((v8 / 'manifest.private.json').read_bytes())['cases'][8]
    v9_case = json.loads((v9 / 'manifest.private.json').read_bytes())['cases'][12]
    negative_task = json.loads(
        Path(v8_case['source_path']).with_name('task.private.json').read_bytes())
    positive_task = json.loads(
        Path(v9_case['source_path']).with_name('task.private.json').read_bytes())
    first_negative = score(
        negative_task,
        artifacts / 'quarantined-negative-first-baseline.private.pptx',
        artifacts / 'quarantined-negative-first-positive.private.pptx')
    stable_negative = score(
        negative_task,
        artifacts / 'quarantined-negative-stable-baseline.private.pptx',
        artifacts / 'quarantined-negative-stable-positive.private.pptx')
    first_positive = score(
        positive_task,
        artifacts / 'quarantined-positive-first-baseline.private.pptx',
        artifacts / 'quarantined-positive-first-positive.private.pptx')
    for failed in (first_negative, first_positive):
        require(failed['status'] == 'scored' and failed['score'] == 0 and
                failed['target_correct'] is True and
                failed['preservation_pass'] is False and
                any('/charts/chart' in part for part in
                    failed['unexpected_parts']),
                'quarantined first-stage chart failure changed')
    require(stable_negative['status'] == 'scored' and
            stable_negative['score'] == 1 and
            stable_negative['preservation_pass'] is True and
            sum(row['changed'] for row in
                stable_negative['per_target'].values()) == 4,
            'stabilized development positive changed')
    quarantines = {
        'negative_chart': v8 / 'quarantine-third-family.private.json',
        'positive_chart': v9 / 'quarantine-fourth-family.private.json',
    }
    for label, path in quarantines.items():
        q = json.loads(path.read_bytes())
        require(q['model_calls'] == q['official_final_admitted'] == 0 and
                q['new_replacement_tasks_required'] == 4,
                label + ' family quarantine changed')
    files = {path.name: sha(path.read_bytes())
             for path in sorted(artifacts.glob('*.private.pptx'))}
    private_receipt = {
        'schema': 'envloop-ppt-web-stabilization-development-private-v1',
        'train_manifest_sha256': sha((train / 'manifest.private.json').read_bytes()),
        'v8_manifest_sha256': sha((v8 / 'manifest.private.json').read_bytes()),
        'v9_manifest_sha256': sha((v9 / 'manifest.private.json').read_bytes()),
        'quarantine_sha256': {key: sha(path.read_bytes())
                              for key, path in quarantines.items()},
        'source_equivalence': source_equivalence,
        'stage_equivalence': stage_equivalence,
        'train_partial_score': partial_score,
        'train_positive_score': positive_score,
        'train_neutral_score': neutral,
        'quarantined_first_negative_chart_score': first_negative,
        'quarantined_stable_negative_chart_score': stable_negative,
        'quarantined_first_positive_chart_score': first_positive,
        'saved_artifact_sha256': files,
        'controller_sha256': {
            'core_v1': sha(args.controller_v1.read_bytes()),
            'neutral_v2': sha(args.controller_v2.read_bytes()),
            'pre_task_open': sha(args.open_helper.read_bytes()),
            'verifier': sha(Path(verify.__file__).read_bytes()),
        },
        'model_calls': 0, 'official_final_admitted': 0,
    }
    receipt_sha = write_new(artifacts / 'stabilization-audit.private.json',
                            private_receipt, 0o600)
    public = {
        'schema': 'envloop-ppt-web-stabilization-development-public-v1',
        'status': 'pre_result_evaluator_and_train_only_no_final_admissions',
        'train_source_to_first_stage_semantics_preserved': True,
        'train_first_to_second_stage_semantics_preserved': True,
        'train_four_target_neutral_saved_state_preserved': True,
        'train_partial_target_changes': 1,
        'train_partial_score': 0,
        'train_four_target_positive_score': 1,
        'train_four_target_positive_preservation_pass': True,
        'quarantined_first_stage_chart_failures': 2,
        'quarantined_stabilized_chart_positive_score': 1,
        'quarantined_source_families_excluded': 2,
        'controller_sha256': private_receipt['controller_sha256'],
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
