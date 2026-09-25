"""Audit all 24 campaigns and 3,000 final slots before report generation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cursibench import full_study_matrix_v1 as matrix
from cursibench import full_study_results_v1 as results
from cursibench import scale_final_v06 as cell_final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--matrix-manifest', type=Path, required=True)
    parser.add_argument('--execution-index', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--bootstrap-replicates', type=int, default=10_000)
    args = parser.parse_args()
    matrix_path = args.matrix_manifest.resolve()
    raw_matrix = matrix_path.read_bytes()
    plan = matrix.build(json.loads(raw_matrix), matrix_path.parent,
                        cell_final.digest(raw_matrix))
    index_path = args.execution_index.resolve()
    audited = results.audit(
        plan, json.loads(index_path.read_bytes()), index_path.parent,
        plan_sha256=cell_final.digest(cell_final.json_bytes(plan)),
        bootstrap_replicates=args.bootstrap_replicates)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(audited, stream, indent=2, sort_keys=True)
        stream.write('\n')
    os.chmod(args.out, 0o600)
    print(json.dumps({'status': 'complete_audited_index',
                      'campaign_count': audited['campaign_count'],
                      'distinct_final_task_identities':
                          audited['distinct_final_task_identities'],
                      'slot_task_result_count': audited['slot_task_result_count'],
                      'provider_invoice_complete':
                          audited['provider_invoice_complete']}, sort_keys=True))


if __name__ == '__main__':
    main()
