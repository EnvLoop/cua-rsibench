"""Audit train-only PowerPoint web persistence and control discrimination.

All source, task and saved artifacts stay evaluator-private. Public output
contains only aggregate properties and SHA-256 bindings, never cloud URLs,
task text, hidden final IDs, or model outcomes.
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
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return sha(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-root', type=Path, required=True)
    parser.add_argument('--index', type=int, required=True)
    parser.add_argument('--private-dir', type=Path, required=True)
    parser.add_argument('--controller', type=Path, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    root, artifacts = args.train_root.resolve(), args.private_dir.resolve()
    require(root.is_relative_to(private) and artifacts.is_relative_to(private)
            and not (artifacts / 'durability-audit.private.json').exists()
            and not args.public_out.exists(),
            'fresh private/public receipts and evaluator-private artifacts required')
    train = json.loads((root / 'manifest.private.json').read_bytes())
    require(train['schema'] == 'envloop-ppt-wdi-train-policy-development-private-v1'
            and 0 <= args.index < len(train['cases']),
            'train-only manifest/index changed')
    task = train['cases'][args.index]
    source = root / 'packages/train_policy_development' / task['task_id'] / 'source.pptx'
    normalized = artifacts / 'v6-normalized-baseline.pptx'
    baseline_raw = normalized.read_bytes()
    source_equivalence = semantic_source_equal(source, normalized)
    oracle = verify.freeze(normalized, task, office_web_normalized=True)
    role_names = {
        'positive': 'positive-saved.private.pptx',
        'near_miss': 'near_miss-saved.private.pptx',
        'fresh_reset': 'fresh_reset-saved.private.pptx',
        'collateral': 'collateral-saved.private.pptx',
    }
    scored = {}
    for role, filename in role_names.items():
        role_copy = artifacts / ('EL-PPT-Train-Role-v1-' +
                                 role.replace('_', '-') + '.pptx')
        require(role_copy.read_bytes() == baseline_raw,
                'train role input is not a fresh normalized baseline copy')
        saved = artifacts / filename
        report = verify.verify(normalized, saved, oracle)
        scored[role] = {
            'score': report['score'],
            'target_changed_count': sum(row['changed'] for row in
                                        report['per_target'].values()),
            'preservation_pass': report['preservation_pass'],
            'saved_sha256': sha(saved.read_bytes()),
        }
    require(scored['positive']['score'] == 1.0 and
            scored['positive']['target_changed_count'] == 4 and
            scored['positive']['preservation_pass'] is True and
            scored['near_miss']['score'] == 0.0 and
            scored['near_miss']['target_changed_count'] == 3 and
            scored['near_miss']['preservation_pass'] is True and
            scored['fresh_reset']['score'] == 0.0 and
            scored['fresh_reset']['target_changed_count'] == 0 and
            scored['fresh_reset']['preservation_pass'] is True and
            scored['collateral']['score'] == 0.0 and
            scored['collateral']['target_changed_count'] == 0 and
            scored['collateral']['preservation_pass'] is False,
            'train GUI control scores or collateral preservation changed')
    early = {}
    for role in ('positive', 'near_miss'):
        raw = (artifacts / f'early_{role}-saved.private.pptx').read_bytes()
        require(raw == baseline_raw,
                'early cloud download no longer demonstrates propagation lag')
        early[role] = {'source_identical': True, 'sha256': sha(raw)}
    private_receipt = {
        'schema': 'envloop-ppt-web-train-durable-controls-private-v1',
        'train_task_id': task['task_id'],
        'train_manifest_sha256': sha((root / 'manifest.private.json').read_bytes()),
        'source_sha256': sha(source.read_bytes()),
        'normalized_baseline_sha256': sha(baseline_raw),
        'source_equivalence': source_equivalence,
        'early_stale_downloads': early,
        'saved_roles': scored,
        'controller_source_sha256': sha(args.controller.read_bytes()),
        'model_calls': 0, 'official_final_admitted': 0,
    }
    receipt_sha = write_new(artifacts / 'durability-audit.private.json',
                            private_receipt, 0o600)
    public = {
        'schema': 'envloop-ppt-web-train-durable-controls-public-v1',
        'status': 'train_only_web_controls_not_final_admission',
        'source_equivalence': source_equivalence,
        'train_target_count': 4,
        'positive_score': scored['positive']['score'],
        'near_miss_score': scored['near_miss']['score'],
        'near_miss_changed_targets': scored['near_miss']['target_changed_count'],
        'fresh_reset_score': scored['fresh_reset']['score'],
        'fresh_reset_changed_targets': scored['fresh_reset']['target_changed_count'],
        'collateral_score': scored['collateral']['score'],
        'collateral_preservation_pass': scored['collateral']['preservation_pass'],
        'initial_downloads_stale': len(early),
        'independent_saved_pptx_readback': True,
        'controller_source_sha256': private_receipt['controller_source_sha256'],
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
