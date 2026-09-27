"""Publish an aggregate-only PowerPoint V5 original-software GUI checkpoint."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ppt_wdi_factory.plan import canonical
from tools.audit_ppt_wdi_web_stabilization_v1 import require, sha, write_new


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private-root', type=Path, required=True)
    parser.add_argument('--staging', type=Path, required=True)
    parser.add_argument('--controller-v5', type=Path, required=True)
    parser.add_argument('--verifier', type=Path, required=True)
    parser.add_argument('--expected-passed', type=int, required=True)
    parser.add_argument('--public-out', type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / 'work').resolve()
    root, staging = args.private_root.resolve(), args.staging.resolve()
    require(root.is_relative_to(private) and staging.is_relative_to(private)
            and not args.public_out.exists() and
            1 <= args.expected_passed <= 100,
            'private inputs and fresh public output required')
    plan_raw = (root / 'candidate-plan.private.json').read_bytes()
    manifest = json.loads((staging / 'manifest.private.json').read_bytes())
    require(manifest['plan_sha256'] == sha(plan_raw) and
            manifest['case_count'] == 100,
            '100-case staging inventory changed')
    controller_hash = sha(args.controller_v5.read_bytes())
    verifier_hash = sha(args.verifier.read_bytes())
    receipts = sorted(staging.glob('case-*/v5-gui-control-audit.private.json'))
    require(len(receipts) == args.expected_passed,
            'completed per-ID GUI-control count changed')
    commitments = []
    for path in receipts:
        raw = path.read_bytes()
        item = json.loads(raw)
        index = item['index']
        require(path.parent.name == f'case-{index:03d}' and
                item['task_id'] == manifest['cases'][index]['task_id'] and
                item['plan_sha256'] == sha(plan_raw) and
                item['controller_v5_sha256'] == controller_hash and
                item['verifier_sha256'] == verifier_hash and
                item['per_id_gui_controls_passed'] is True and
                item['model_calls'] == item['official_final_admitted'] == 0 and
                item['scores'] == {
                    'phase1_positive': 1, 'neutral_stability': 0,
                    'phase2_positive': 1, 'fresh_positive': 1,
                    'near_miss': 0, 'fresh_reset': 0, 'collateral': 0,
                },
                'saved-state GUI control receipt changed')
        commitments.append(sha(raw))
    public = {
        'schema': 'envloop-ppt-v5-final-gui-progress-public-v1',
        'status': 'development_gui_controls_passed_official_admission_pending',
        'candidate_final_total': 100,
        'individual_original_powerpoint_web_gui_controls_passed': len(receipts),
        'independent_saved_pptx_scoring': True,
        'fresh_copy_positive_near_miss_reset_and_collateral_controls': True,
        'controller_v5_sha256': controller_hash,
        'verifier_sha256': verifier_hash,
        'private_receipt_commitment_sha256': sha(canonical(commitments)),
        'official_final_admitted': 0,
        'model_calls': 0,
        'researcher_campaigns': 0,
    }
    digest = write_new(args.public_out, public, 0o644)
    print(json.dumps({'status': public['status'],
                      'gui_controls_passed': len(receipts),
                      'public_receipt_sha256': digest,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
