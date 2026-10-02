"""Unchanged v17 transfer/executor with one common passive-readiness bound."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
from unittest.mock import patch

from . import selection_control_bounded_worker_v17 as inherited
from . import selection_control_readiness_worker_v12 as original_readiness_worker
from . import selection_control_readiness_epoch_v18 as epoch
from . import pre_observation_readiness_v18 as readiness


@contextmanager
def context(value=None, *, live=False):
    with patch.object(inherited, 'epoch', epoch), \
         patch.object(original_readiness_worker, 'readiness', readiness), \
         inherited.context(value, live=live):yield


def run_trio(*, freeze_path, permit_path, enable_paid_controls=False):
    if enable_paid_controls is not True:raise ValueError('Paid passive readiness controls disabled before private reads')
    value = epoch.validate(freeze_path)
    with context(value, live=True):
        return inherited.inherited.core_worker.run_trio(freeze_path=freeze_path, permit_path=permit_path, enable_paid_controls=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', required=True, type=Path)
    parser.add_argument('--permit', required=True, type=Path)
    parser.add_argument('--enable-paid-controls', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run_trio(freeze_path=args.freeze, permit_path=args.permit,
                             enable_paid_controls=args.enable_paid_controls), sort_keys=True))


if __name__ == '__main__':main()
