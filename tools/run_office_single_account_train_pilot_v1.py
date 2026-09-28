"""Audit saved/downloaded original Office train evidence without cloud calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.office_single_account_train_pilot_v1 import (
    SingleAccountPilotError, audit,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path,
                        default=Path.cwd() / 'work')
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.spec, args.evidence, args.out,
                       work_root=args.work_root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            'status': 'refused',
            'reason_type': type(exc).__name__,
            'reason_code': str(exc) if isinstance(
                exc, SingleAccountPilotError) else None,
            'official_final_credit': 0,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
