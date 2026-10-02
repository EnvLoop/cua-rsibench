"""Capture read-only Tinker usage privately; emit only safe aggregate counts."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from cursibench import full_study_tinker_billing_v1 as billing
from cursibench.full_study_tinker_preflight_v1 import sha256


ROOT = Path(__file__).resolve().parents[1]


def _when(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--starting-on", required=True, type=_when,
                        help="UTC hour-aligned inclusive RFC3339 timestamp")
    parser.add_argument("--ending-before", required=True, type=_when,
                        help="UTC hour-aligned exclusive RFC3339 timestamp")
    parser.add_argument("--out", required=True, type=Path,
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
        receipt = billing.collect_read_only(
            ROOT, args.out, start=args.starting_on,
            end=args.ending_before)
        raw = (args.out / "response.private.json").read_bytes()
        public = billing.public_summary(
            receipt, raw,
            private_receipt_sha256=sha256(
                (args.out / "receipt.private.json").read_bytes()))
        if args.public_out is not None:
            args.public_out.parent.mkdir(parents=True, exist_ok=True)
            with args.public_out.open("x", encoding="utf-8") as stream:
                json.dump(public, stream, sort_keys=True, indent=2)
                stream.write("\n")
    except Exception as exc:
        print(json.dumps({"status": "read_only_billing_unavailable",
                          "error_type": type(exc).__name__,
                          "training_or_sampling_provider_calls": 0}),
              file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(public, sort_keys=True))


if __name__ == "__main__":
    main()
