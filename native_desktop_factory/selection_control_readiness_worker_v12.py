"""Process-local passive-readiness binding on unchanged selection scripts."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import json
from pathlib import Path
from unittest.mock import patch

from . import v066_post_enter_control_attempt_v9 as worker
from . import v066_post_enter_control_audit_v9 as audit
from . import qwen_v066_adapter_v4_strict as strict
from . import selection_control_scripts_v10 as scripts
from . import selection_control_readiness_epoch_v12 as epoch
from . import pre_observation_readiness_v12 as readiness
from .v066_control_plan import compile_script

ORIGINAL_AUDIT_ATTEMPT = audit.audit_attempt


def audit_attempt(*, value, row, attempt):
    result = ORIGINAL_AUDIT_ATTEMPT(value=value, row=row, attempt=attempt)
    # The inherited auditor already opened this exact consumed task oracle.
    # No future selection/final gold is accessed for readiness verification.
    from . import admit
    inventory = json.loads(epoch.private(Path(value['candidate_root']) / 'candidate-inventory.json'))
    full = next(r for r in inventory['tasks'] if r['task_id'] == row['task_id'])
    directory, _baseline, oracle = admit._package(Path(value['candidate_root']), full)
    actions, _guards = compile_script(scripts.actor_script(directory, oracle, attempt))
    root = Path(value['attempts_root'])
    out = root / row['task_id'] / attempt
    readiness.audit_samples(root, out, actions, json.loads(epoch.private(out / 'receipt.json')))
    return result


@contextmanager
def context():
    with ExitStack() as stack:
        for module in (worker, audit):
            stack.enter_context(patch.object(module, 'epoch', epoch))
            stack.enter_context(patch.object(module, 'actor_script', scripts.actor_script))
        stack.enter_context(patch.object(strict, 'observe', readiness.observe))
        stack.enter_context(patch.object(strict, 'dispatch', readiness.dispatch))
        stack.enter_context(patch.object(audit, 'audit_attempt', audit_attempt))
        yield


def run_trio(*, freeze_path, permit_path, enable_paid_controls=False):
    if enable_paid_controls is not True:
        raise ValueError('Paid readiness successor remains closed')
    value = epoch.validate(freeze_path)
    row = epoch.next_row(value)
    epoch.require(row is not None, 'All v12 control trios are complete')
    epoch.checked_permit(freeze_path, permit_path, value, row)
    with context():
        return worker.run_trio(freeze_path=freeze_path, permit_path=permit_path, enable_paid_controls=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze', required=True, type=Path)
    p.add_argument('--permit', required=True, type=Path)
    p.add_argument('--enable-paid-controls', action='store_true')
    a = p.parse_args()
    print(json.dumps(run_trio(freeze_path=a.freeze, permit_path=a.permit,
                              enable_paid_controls=a.enable_paid_controls), sort_keys=True))


if __name__ == '__main__':
    main()
