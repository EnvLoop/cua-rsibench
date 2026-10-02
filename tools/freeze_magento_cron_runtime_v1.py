"""Freeze the revised Magento runtime only after complete train GUI controls.

This creates a private non-scoring receipt. It does not start Docker or launch
any candidate; the full 100-case sweep is a separate, later operator action.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from magento_catalog_factory.plan import ROOT, require
from tools.magento_cron_runtime_contract_v1 import (
    FINAL_PLAN, TRAIN_PLAN, TRAIN_RETRY_DIR, build_freeze, sha,
)


PROBE_DIR = ROOT / 'work/magento-original/cron-never-autostart-train-probe-20260927-v2'
TRAIN_DIR = ROOT / TRAIN_RETRY_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train-plan-sha256', required=True)
    parser.add_argument('--final-plan-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    out = args.out.resolve()
    require(out.is_relative_to(private) and not out.exists() and
            sha((ROOT / TRAIN_PLAN).read_bytes()) == args.train_plan_sha256 and
            sha((ROOT / FINAL_PLAN).read_bytes()) == args.final_plan_sha256,
            'unchanged separate private plans and fresh private freeze path required')
    frozen = build_freeze(ROOT, PROBE_DIR, TRAIN_DIR,
                          args.train_plan_sha256, args.final_plan_sha256)
    out.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = (json.dumps(frozen, indent=2, sort_keys=True) + '\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({'status': frozen['status'],
                      'receipt_sha256': sha(raw),
                      'runtime_fingerprint_sha256': frozen['runtime_fingerprint_sha256'],
                      'historical_controls_reused': 0,
                      'fresh_candidate_controls_required': 100,
                      'official_final_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
