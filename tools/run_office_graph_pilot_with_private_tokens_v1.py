"""Run one explicit Graph pilot action with private owner-only token files.

This wrapper prevents shell history and child command arguments from exposing
bearer values. It never starts login and does not read browser state. The
underlying pilot still blocks selection/final writes and unknown accounts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.office_graph_msal_device_code_v1 import (
    DeviceAuthError, with_private_tokens,
)
from tools.run_office_graph_personal_bootstrap_pilot_v1 import (
    main as pilot_main,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path,
                        default=Path.cwd() / 'work')
    parser.add_argument('--auth-dir', type=Path, required=True)
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reset-copy', type=Path)
    parser.add_argument('command', choices=(
        'check', 'invite', 'reconcile-invite', 'delete',
        'reconcile-delete', 'abort-delete', 'finalize',
        'prepare-reset', 'snapshot'))
    args = parser.parse_args(argv)
    arguments = [
        '--work-root', str(args.work_root),
        '--spec', str(args.spec),
        '--out', str(args.out),
    ]
    if args.reset_copy is not None:
        arguments += ['--reset-copy', str(args.reset_copy)]
    arguments.append(args.command)
    try:
        return with_private_tokens(
            auth_dir=args.auth_dir, work_root=args.work_root,
            run=lambda: pilot_main(arguments))
    except Exception as exc:
        print(json.dumps({
            'status': 'refused',
            'reason_type': type(exc).__name__,
            'reason_code': str(exc) if isinstance(exc, DeviceAuthError)
                           else None,
        }, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
