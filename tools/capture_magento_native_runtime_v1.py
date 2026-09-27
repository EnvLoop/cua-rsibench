"""Bind one frozen Magento baseline to its live app and native search pair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from magento_catalog_factory.plan import ROOT, require
from magento_catalog_factory.seed import CONTEXT, check_clone, load_case
from magento_catalog_factory.verify import (
    NATIVE_SEARCH_HOST, NATIVE_SEARCH_IMAGE, NATIVE_SEARCH_NETWORK,
    check_baseline, check_native_search_sidecar,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--task-id', required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    private = (ROOT / 'work').resolve()
    baseline_path, out = args.baseline.resolve(), args.out.resolve()
    require(baseline_path.is_relative_to(private) and baseline_path.is_file() and
            out.is_relative_to(private) and not out.exists(),
            'private baseline and new runtime receipt under ignored work/ required')
    case = load_case(args.plan, args.plan_sha256, args.task_id)
    baseline_bytes = baseline_path.read_bytes()
    baseline = json.loads(baseline_bytes)
    check_baseline(case, baseline)
    app = check_clone('envloop-magento-original-control', 7794, 7795)
    check_native_search_sidecar('envloop-magento-original-control')
    raw = subprocess.run(['docker', '--context', CONTEXT, 'inspect',
                          NATIVE_SEARCH_HOST], capture_output=True,
                         text=True, check=True, timeout=30).stdout
    sidecar = json.loads(raw)[0]
    receipt = {
        'schema': 'envloop-magento-native-sidecar-runtime-private-v1',
        'app': app,
        'sidecar_image_sha256': NATIVE_SEARCH_IMAGE,
        'sidecar_id_sha256': hashlib.sha256(sidecar['Id'].encode()).hexdigest(),
        'network': NATIVE_SEARCH_NETWORK,
        'baseline_sha256': hashlib.sha256(baseline_bytes).hexdigest(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    output = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(output)
    print(json.dumps({'status': 'private_runtime_bound',
                      'receipt_sha256': hashlib.sha256(output).hexdigest(),
                      'official_final_tasks_admitted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
