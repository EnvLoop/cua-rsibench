"""Explicit evaluator-only Graph permission lease commands.

No command invents a capability receipt or token. `invite` and `delete` are
one-shot external writes after source/account gates; reconciliation is read-
only. Public terminal output contains hashes and status, never account IDs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.office_graph_one_file_lease_v1 import (
    GraphLeaseError, OneFileGraphLease,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path,
                        default=Path.cwd() / 'work')
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('command', choices=(
        'check', 'invite', 'reconcile-invite', 'delete',
        'reconcile-delete', 'snapshot'))
    args = parser.parse_args(argv)
    try:
        controller = OneFileGraphLease(
            args.spec, args.out, work_root=args.work_root)
        if args.command in ('check', 'snapshot'):
            result = controller.snapshot()
        elif args.command == 'invite':
            result = controller.invite()
        elif args.command == 'reconcile-invite':
            result = controller.reconcile_invite()
        elif args.command == 'delete':
            result = controller.delete()
        else:
            result = controller.reconcile_delete()
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({
            'state': 'refused',
            'reason_type': type(exc).__name__,
            'reason_code': str(exc) if isinstance(exc, GraphLeaseError)
                           else None,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
