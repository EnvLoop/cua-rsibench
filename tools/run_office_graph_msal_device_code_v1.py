"""Operator-invoked personal Microsoft device login; never prints tokens.

`check-config` is offline. `login-owner` and `login-actor` each require an
interactive terminal and initiate one bounded Microsoft device-code flow.
The operator enters the displayed code on Microsoft's own login page.
`finalize-scopes` only reads private role proofs and access-token files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from tools.office_graph_msal_device_code_v1 import (
    DeviceAuthError, SCOPES, finalize_scopes, load_app_config,
    login_role, _sha,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path,
                        default=Path.cwd() / 'work')
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--auth-dir', type=Path, required=True)
    parser.add_argument('command', choices=(
        'check-config', 'login-owner', 'login-actor',
        'finalize-scopes'))
    args = parser.parse_args(argv)
    try:
        if args.command == 'check-config':
            config, digest = load_app_config(
                args.config, args.work_root)
            result = {
                'status': 'private_public_client_config_valid',
                'config_sha256': digest,
                'client_id_sha256': _sha(config['client_id']),
                'authority': config['authority'],
                'requested_scopes': SCOPES,
                'provider_calls': 0,
            }
        elif args.command == 'finalize-scopes':
            result = finalize_scopes(
                config_path=args.config,
                auth_dir=args.auth_dir,
                work_root=args.work_root)
        else:
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                raise DeviceAuthError(
                    'office_oauth_interactive_terminal_required')
            role = args.command.removeprefix('login-')
            def present(uri: str, code: str) -> None:
                print('Open ' + uri + ' and enter code ' + code,
                      flush=True)
            result = login_role(
                role=role, config_path=args.config,
                output_dir=args.auth_dir / role,
                work_root=args.work_root,
                present=present)
        print(json.dumps(result, sort_keys=True))
        return 0
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
