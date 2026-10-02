"""Unchanged GUI executor with the common projected runtime attestation."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
from unittest.mock import patch

from . import selection_control_accounting_worker_v13 as inherited
from . import selection_control_structural_epoch_v16 as epoch
from . import structural_guest_attestation_v16 as common
from . import v066_post_enter_control_audit_v9 as audit
from . import v066_post_enter_control_attempt_v9 as core_worker

BASE_AUDIT = inherited.inherited.audit_attempt


def audit_attempt(*, value, row, attempt):
    result = BASE_AUDIT(value=value, row=row, attempt=attempt)
    out = Path(value['attempts_root']) / row['task_id'] / attempt
    command = json.loads(epoch.private(out / 'guest-probe-command-v16.private.json'))
    observed = json.loads(command['stdout']); reference = json.loads(Path(value['guest_public']).read_bytes())
    attestation = common.verify(observed, (out / 'guest-content-files-v16.jsonl.gz').read_bytes(), reference)
    if command['exit_code'] != 0 or json.loads(epoch.private(out / 'structural-attestation-v16.private.json')) != attestation:
        raise ValueError('Raw/projected structural runtime evidence changed')
    return result


class Commands:
    def __init__(self, raw, sandbox, reference):self.raw = raw; self.sandbox = sandbox; self.reference = reference
    def __getattr__(self, name):return getattr(self.raw, name)
    def run(self, command, *args, **kwargs):
        if command != 'sudo -n python3 /tmp/native-guest-content-probe-v066.py':return self.raw.run(command, *args, **kwargs)
        try:result = self.raw.run(command, *args, **kwargs)
        except Exception as exc:
            if not all(hasattr(exc, key) for key in ('exit_code', 'stdout', 'stderr')):raise
            result = exc
        common.capture_result(self.sandbox, result, root=Path(os.environ['ENVLOOP_DESKTOP_V4_ATTEMPTS_ROOT']),
                              out=Path(os.environ['ENVLOOP_DESKTOP_V4_ATTEMPT_DIR']), reference=self.reference)
        return result  # Actual projected stdout is preserved; no legacy raw hash is fabricated.


class AttestingSandbox:
    def __init__(self, raw, reference):
        self.raw = raw; self.commands = Commands(raw.commands, raw, reference)
    def __getattr__(self, name):return getattr(self.raw, name)


@contextmanager
def context(value=None, *, live=False):
    with patch.object(inherited, 'epoch', epoch), inherited.context(), patch.object(audit, 'audit_attempt', audit_attempt):
        if not live:
            yield; return
        from e2b_desktop import Sandbox
        reference = json.loads(Path(value['guest_public']).read_bytes())
        create = Sandbox.create; generated = common.script()
        with patch.object(Sandbox, 'create', lambda *args, **kwargs: AttestingSandbox(create(*args, **kwargs), reference)), \
             patch.object(common.legacy, 'GUEST_CONTENT_PROBE', generated):
            yield


def run_trio(*, freeze_path, permit_path, enable_paid_controls=False):
    if enable_paid_controls is not True:raise ValueError('Paid structural controls disabled before private reads')
    value = epoch.validate(freeze_path)
    with context(value, live=True):return core_worker.run_trio(freeze_path=freeze_path, permit_path=permit_path, enable_paid_controls=True)


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--freeze', type=Path, required=True)
    p.add_argument('--permit', type=Path, required=True); p.add_argument('--enable-paid-controls', action='store_true'); a = p.parse_args()
    print(json.dumps(run_trio(freeze_path=a.freeze, permit_path=a.permit, enable_paid_controls=a.enable_paid_controls), sort_keys=True))


if __name__ == '__main__':main()
