"""Inspect installed E2B Desktop fork wrapping with a mocked provider method.

Run only with a local e2b-desktop 2.2.0 / e2b 2.51.0 installation. This
probes Python-side child construction, not VM memory, GUI, auth, or ACLs.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
from unittest.mock import patch


def main() -> None:
    from e2b.api import SandboxCreateResponse
    from e2b.sandbox_sync.sandbox_api import SandboxApi
    from e2b_desktop import Sandbox

    assert importlib.metadata.version('e2b') == '2.51.0'
    assert importlib.metadata.version('e2b-desktop') == '2.2.0'
    source = SandboxCreateResponse(
        sandbox_id='offline-child-1234',
        sandbox_domain='offline.e2b.app',
        envd_version='0.2.0',
        envd_access_token=None,
        traffic_access_token=None,
    )
    with patch.object(SandboxApi, '_cls_fork', return_value=[source]) as mocked:
        children = Sandbox._cls_fork_sandbox(
            'offline-parent-1234', count=1, api_key='offline-only')
        assert mocked.call_count == 1
    assert len(children) == 1 and not isinstance(children[0], Exception)
    child = children[0]
    assert child.sandbox_id == 'offline-child-1234'
    source_paths = {
        'e2b_sync_sandbox': Path(inspect.getfile(Sandbox.__mro__[1])),
        'e2b_desktop_sandbox': Path(inspect.getfile(Sandbox)),
    }
    print(json.dumps({
        'schema': 'envloop-office-e2b-wrapper-offline-probe-v1',
        'provider_requests': 0,
        'sdk_version': importlib.metadata.version('e2b'),
        'desktop_version': importlib.metadata.version('e2b-desktop'),
        'mocked_fork_invocations': mocked.call_count,
        'child_is_desktop_subclass': isinstance(child, Sandbox),
        'child_has_display_wrapper': hasattr(child, '_display'),
        'child_has_vnc_wrapper': hasattr(child, '_Sandbox__vnc_server'),
        'source_sha256': {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in source_paths.items()
        },
        'live_gui_or_acl_verified': False,
        'official_final_admitted': 0,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
