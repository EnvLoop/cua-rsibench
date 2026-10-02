"""Use the unchanged v12 worker with a scoped v13 accounting/source binding."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import argparse
import json

from . import selection_control_readiness_worker_v12 as inherited
from . import selection_control_accounting_epoch_v13 as epoch


@contextmanager
def context():
    with patch.object(inherited, 'epoch', epoch), inherited.context():yield


def run_trio(*, freeze_path, permit_path, enable_paid_controls=False):
    if enable_paid_controls is not True:raise ValueError('Paid v13 controls are disabled before private reads')
    with context():return inherited.run_trio(freeze_path=freeze_path, permit_path=permit_path, enable_paid_controls=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze', required=True, type=Path); p.add_argument('--permit', required=True, type=Path)
    p.add_argument('--enable-paid-controls', action='store_true'); a = p.parse_args()
    print(json.dumps(run_trio(freeze_path=a.freeze, permit_path=a.permit, enable_paid_controls=a.enable_paid_controls), sort_keys=True))


if __name__ == '__main__':main()
