"""Separate v0.6.1 Magento model pilot with minimal student action output.

This imports a pinned copy of the v0.6 trusted browser/evaluator host without
editing its code or the first paid result. Only the model-facing render/parse
boundary changes. The host still applies its strict task/frame-bound validator,
GUI dispatch, local-origin guard, read-only business check, and exact evaluator.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path

from cursibench.scale_action_contract import VERSION as TRUSTED_ACTION_VERSION
from cursibench.scale_action_output_v061 import (
    OUTPUT_VERSION, normalize_model_action, render_for_model,
)

VERSION = 'magento-model-pilot-v0.6.1'
CAMPAIGN_ID = 'magento-base-pilot-v2'
ROOT = Path(__file__).resolve().parents[1]
BASE_RUNNER = ROOT / 'tools/run_magento_model_pilot_v06.py'
BASE_RUNNER_SHA256 = '25f32928ff11e7ebdeb426be943680ddc8e05fa72f1caea3117a18a67bdebeeb'


def _load_host():
    actual = hashlib.sha256(BASE_RUNNER.read_bytes()).hexdigest()
    if actual != BASE_RUNNER_SHA256:
        raise RuntimeError('pinned_v06_host_changed')
    spec = importlib.util.spec_from_file_location('pinned_magento_v06_host', BASE_RUNNER)
    host = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host)
    strict_validator = host.validate_action

    def validate_output(raw, observation, *, current_frame_id):
        if type(raw) is str:
            return normalize_model_action(raw, observation,
                                          current_frame_id=current_frame_id)
        return strict_validator(raw, observation,
                                current_frame_id=current_frame_id)

    # This module object is private to the current process. The v0.6 source,
    # earlier journal, and earlier result remain byte-for-byte untouched.
    host.VERSION = VERSION
    host.CAMPAIGN_ID = CAMPAIGN_ID
    host.render_for_proxy = render_for_model
    host.validate_action = validate_output
    return host


host = _load_host()
SOURCE = host.SOURCE


async def run(source: Path, out: Path, adapter_factory):
    out = Path(out).resolve()
    result = await host.run(source, out, adapter_factory)
    host.smoke.write(out / 'boundary.json', {
        'pilot_version': VERSION,
        'model_output_version': OUTPUT_VERSION,
        'trusted_action_version': TRUSTED_ACTION_VERSION,
        'campaign_id': CAMPAIGN_ID,
        'base_runner_sha256': BASE_RUNNER_SHA256,
        'output_boundary_sha256': hashlib.sha256(
            (ROOT / 'src/cursibench/scale_action_output_v061.py').read_bytes()).hexdigest(),
        'runner_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'result_sha256': hashlib.sha256((out / 'result.json').read_bytes()).hexdigest(),
        'first_paid_pilot_reused': False,
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    factory = host.LiveAdapterFactory()
    try:
        result = asyncio.run(run(args.source, args.out, factory))
        print(json.dumps({
            'version': VERSION, 'output_version': OUTPUT_VERSION,
            'status': result['status'], 'score': result['score'],
            'pilot_task_complete': result.get('pilot_task_complete'),
            'failure_class': result.get('failure_class'),
            'failure_code': result.get('failure_code'),
            'max_actions': host.MAX_ACTIONS,
        }, sort_keys=True), flush=True)
        raise SystemExit(0 if result['status'] == 'completed' else 2)
    finally:
        factory.close('success' if 'result' in locals() and result['status'] == 'completed' else 'errored')


if __name__ == '__main__':
    main()
