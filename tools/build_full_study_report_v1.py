"""Build the English result PDF only after every full-study publication gate passes.

Example (all inputs are private, hash-bound execution evidence)::

  PYTHONPATH=src python tools/build_full_study_report_v1.py \
    --matrix-manifest work/full-study/matrix.json \
    --execution-index work/full-study/execution-index.json \
    --audited-summary work/full-study/audited-results.json \
    --telemetry-index work/full-study/final-attempt-telemetry.json \
    --trajectory-index work/full-study/campaign-trajectories.json \
    --independent-review work/full-study/independent-release-audit.json \
    --out-dir work/full-study/paper-review
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cursibench.full_study_paper_v1 import build_report
from cursibench.full_study_publication_v1 import load_publication_data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for option in (
        'matrix-manifest', 'execution-index', 'audited-summary',
        'telemetry-index', 'trajectory-index', 'independent-review',
        'out-dir',
    ):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    try:
        data = load_publication_data(
            matrix_manifest=args.matrix_manifest.resolve(),
            execution_index=args.execution_index.resolve(),
            audited_summary=args.audited_summary.resolve(),
            telemetry_index=args.telemetry_index.resolve(),
            trajectory_index=args.trajectory_index.resolve(),
            independent_review=args.independent_review.resolve(),
        )
        manifest = build_report(data, args.out_dir)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(json.dumps({'status': 'refused', 'reason': str(exc)},
                         sort_keys=True), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps({
        'status': 'built_for_private_review',
        'study_id': manifest['study_id'],
        'pdf': str((args.out_dir / 'EnvLoop-Full-Computer-Use-Study.pdf').resolve()),
        'files': len(manifest['file_sha256']),
        'publication_boundary': manifest['publication_boundary'],
    }, sort_keys=True))


if __name__ == '__main__':
    main()
