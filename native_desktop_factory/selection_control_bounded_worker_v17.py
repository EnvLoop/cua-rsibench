"""Unchanged inherited control entry with uniform bounded guest transfer."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_structural_worker_v16 as inherited
from . import selection_control_bounded_epoch_v17 as epoch
from . import bounded_guest_transport_v17 as transport


@contextmanager
def context(value=None, *, live=False):
    # Outer create patch is captured by v16 before AttestingSandbox is made.
    # Its Commands.sandbox therefore sees BoundedFiles during capture_result.
    with patch.object(inherited, 'epoch', epoch):
        if live:
            with transport.create_context(), inherited.context(value, live=True):yield
        else:
            with inherited.context():yield


def run_trio(*, freeze_path, permit_path, enable_paid_controls=False):
    if enable_paid_controls is not True:raise ValueError('Paid bounded controls disabled before private reads')
    value = epoch.validate(freeze_path)
    with context(value, live=True):
        return inherited.core_worker.run_trio(freeze_path=freeze_path, permit_path=permit_path, enable_paid_controls=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', required=True, type=Path)
    parser.add_argument('--permit', required=True, type=Path)
    parser.add_argument('--enable-paid-controls', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_trio(freeze_path=args.freeze, permit_path=args.permit,
                             enable_paid_controls=args.enable_paid_controls), sort_keys=True))


if __name__ == '__main__':main()
