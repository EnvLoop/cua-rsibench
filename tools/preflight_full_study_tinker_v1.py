"""Read-only authenticated Tinker Qwen preflight; never starts a campaign."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cursibench.full_study_tinker_preflight_v1 import (
    PreflightError, run_read_only,
)


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path,
                        help='Fresh private directory under repository work/')
    args = parser.parse_args()
    try:
        receipt = run_read_only(ROOT, args.out)
    except PreflightError as exc:
        print(json.dumps({'status': 'blocked', 'code': str(exc),
                          'training_or_sampling_provider_calls': 0}),
              file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as exc:
        print(json.dumps({'status': 'blocked',
                          'error_type': type(exc).__name__,
                          'training_or_sampling_provider_calls': 0}),
              file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps({
        'status': 'read_only_model_capabilities_verified',
        'model': receipt['model'],
        'tinker_sdk_version': receipt['tinker_sdk_version'],
        'published_models_json_sha256':
            receipt['catalog']['published_models_json_sha256'],
        'action_bundle_sha256': receipt['action_bundle']['bundle_sha256'],
        'trainable': receipt['provider']['exact_model_trainable'],
        'sampleable': receipt['provider']['exact_model_sampleable'],
        'campaign_dispatch_authorized': False,
        'official_final_results': 0,
    }, sort_keys=True))


if __name__ == '__main__':
    main()
