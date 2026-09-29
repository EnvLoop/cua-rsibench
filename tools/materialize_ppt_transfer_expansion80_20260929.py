"""Resume the frozen 80-case WDI train-only direct-file build."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from ppt_wdi_factory import plan as ppt, verify
from tools import office_transfer_source_gate_v1 as gate


PILOT_SHA = "34a584f51ee2254d726c3a37e106e18efeaf3a41b515a72766b57407876a6499"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def write_new(path: Path, raw: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def materialize(args: argparse.Namespace) -> dict:
    private = args.private_root.resolve()
    require(private.is_dir() and not private.is_symlink() and
            private.stat().st_mode & 0o077 == 0 and
            private.is_relative_to((Path.cwd() / "work").resolve()),
            "expansion_private_root_unsafe")
    manifest_raw = (private / "manifest.private.json").read_bytes()
    seed = (private / "seed.private").read_bytes()
    pilot_raw = (args.pilot_private_root / "manifest.private.json").read_bytes()
    pilot_seed = (args.pilot_private_root / "seed.private").read_bytes()
    require(sha256(pilot_raw).hexdigest() == PILOT_SHA and seed == pilot_seed,
            "frozen_pilot_seed_or_manifest_changed")
    pilot_plan = json.loads(pilot_raw)
    plan = gate.ppt_transfer_plan(
        seed, args.official_csv_root, args.original_v13_plan,
        args.original_v13_plan, args.future_reserve_queue,
        args.calibration_boundary, args.historical_plan_dir,
        stage="expansion", pilot_plan=pilot_plan)
    require(manifest_raw == ppt.canonical(plan) and
            len(plan["rows"]) == 80 and
            not (private / "offline-controls.private.json").exists() and
            not args.public_out.exists(),
            "frozen_expansion_plan_changed_or_receipt_already_exists")
    rows = gate.materialize_ppt_transfer(
        plan, args.official_csv_root, private, workers=args.workers)
    receipt = {
        "schema": "envloop-ppt-transfer-offline-controls-private-v1",
        "plan_sha256": sha256(manifest_raw).hexdigest(),
        "builder_sha256": sha256(Path(
            "ppt_wdi_factory/build_train_transfer_deck.mjs").read_bytes()).hexdigest(),
        "verifier_sha256": sha256(Path(verify.__file__).read_bytes()).hexdigest(),
        "results": rows,
        "offline_controls_passed": len(rows),
        "office_web_gui_admitted": 0,
    }
    require(len(rows) == 80, "eighty_saved_artifact_controls_required")
    receipt_raw = ppt.canonical(receipt)
    write_new(private / "offline-controls.private.json", receipt_raw, 0o600)
    public = gate.ppt_public_receipt(plan)
    public.update({
        "status": "train_only_offline_controls_passed_not_gui_admitted",
        "offline_control_passed": 80,
        "private_offline_receipt_sha256": sha256(receipt_raw).hexdigest(),
    })
    write_new(args.public_out,
              (json.dumps(public, sort_keys=True, indent=2) + "\n").encode(),
              0o644)
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--pilot-private-root", type=Path, required=True)
    parser.add_argument("--official-csv-root", type=Path, required=True)
    parser.add_argument("--original-v13-plan", type=Path, required=True)
    parser.add_argument("--future-reserve-queue", type=Path, required=True)
    parser.add_argument("--historical-plan-dir", type=Path, required=True)
    parser.add_argument("--calibration-boundary", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    result = materialize(args)
    print(json.dumps({"status": result["status"],
                      "offline_control_passed": result["offline_control_passed"],
                      "office_web_gui_admitted": 0,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
