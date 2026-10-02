"""Explicit train-only Graph bootstrap pilot; no command runs automatically.

`check`, `reconcile-*`, `snapshot`, and `finalize` are read-only to Graph.
`invite`, `delete`, and explicit `abort-delete` each send at most one write after a
private intent is durable. The CLI never prints account IDs, URLs, or tokens.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.office_graph_personal_bootstrap_pilot_v1 import (
    PersonalGraphBootstrapPilot,
)
from tools.office_graph_one_file_lease_v1 import GraphLeaseError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path,
                        default=Path.cwd() / 'work')
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reset-copy', type=Path)
    parser.add_argument('command', choices=(
        'check', 'invite', 'reconcile-invite', 'delete',
        'reconcile-delete', 'abort-delete', 'finalize',
        'prepare-reset', 'snapshot'))
    args = parser.parse_args(argv)
    try:
        pilot = PersonalGraphBootstrapPilot(
            args.spec, args.out, work_root=args.work_root)
        if args.command == 'prepare-reset':
            if args.reset_copy is None:
                raise GraphLeaseError(
                    'graph_pilot_reset_copy_binding_required')
            result = pilot.prepare_matching_reset_copy(
                args.reset_copy)
        else:
            result = {
                'check': pilot.check,
                'invite': pilot.invite,
                'reconcile-invite': pilot.reconcile_invite,
                'delete': pilot.delete,
                'reconcile-delete': pilot.reconcile_delete,
                'abort-delete': pilot.abort_delete_uncertain_grant,
                'finalize': pilot.finalize,
                'snapshot': pilot.snapshot,
            }[args.command]()
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
