"""Validate one qualified v0.6 cell and persist an offline final-evaluation plan.

Example:
  python tools/prepare_scale_final_v06.py --manifest cell-final.json --out work/v0.6-final/cell-slot

This command makes no provider, E2B, application, or model calls.
"""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from cursibench.scale_final_v06 import prepare  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.out), sort_keys=True))


if __name__ == '__main__':
    main()
