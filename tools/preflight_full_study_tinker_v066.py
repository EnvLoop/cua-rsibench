"""Authenticate a read-only Qwen/v0.6.6 preflight; publish safe aggregates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from cursibench import full_study_tinker_preflight_v066 as preflight
from cursibench.full_study_tinker_preflight_v1 import sha256


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True,
                        help="Fresh private directory under repository work/")
    parser.add_argument("--public-out", type=Path,
                        help="Fresh field-limited receipt under docs/evidence/")
    args = parser.parse_args()
    args.out = args.out.absolute()
    if args.public_out is not None:
        target = args.public_out.absolute()
        if (not target.parent.resolve().is_relative_to(
                (ROOT / "docs/evidence").resolve()) or
                target.exists() or target.is_symlink()):
            parser.error("public receipt requires a fresh docs/evidence/ path")
    try:
        receipt = preflight.run_read_only(ROOT, args.out)
        private_bytes = (args.out / "receipt.private.json").read_bytes()
        public = preflight.public_summary(
            ROOT, receipt, private_receipt_sha256=sha256(private_bytes))
        if args.public_out is not None:
            args.public_out.parent.mkdir(parents=True, exist_ok=True)
            with args.public_out.open("x", encoding="utf-8") as stream:
                json.dump(public, stream, sort_keys=True, indent=2)
                stream.write("\n")
    except Exception as exc:
        print(json.dumps({"status": "blocked", "error_type":
                          type(exc).__name__,
                          "training_or_sampling_provider_calls": 0}),
              file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(public, sort_keys=True))


if __name__ == "__main__":
    main()
