"""Freeze an offline 4 x 6 x 100 study plan after all 30 slots qualify.

Example:
  PYTHONPATH=src python tools/prepare_full_study_matrix_v1.py \
    --manifest work/full-study/matrix.json --out work/full-study/prepared

This command makes no provider, E2B, application, or model calls. Candidate
task inventories fail closed; only 100-task qualified cell manifests pass.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench.full_study_matrix_v1 import prepare  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.out), sort_keys=True))


if __name__ == '__main__':
    main()
