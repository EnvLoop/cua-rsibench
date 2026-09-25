"""Prepare a qualified 24-campaign computer-use study without dispatching it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cursibench.full_study_pre_campaign_v1 import prepare


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.manifest, args.out), sort_keys=True))


if __name__ == '__main__':
    main()
