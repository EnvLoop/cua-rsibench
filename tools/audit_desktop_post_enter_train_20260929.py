"""Replay only retained public-train Calc Enter transitions, with no provider.

The receipt SHA and split are checked before any frame is opened. No final
task or model trajectory is accepted as a calibration input.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path

from native_desktop_factory.post_enter_settle_candidate_v1 import (
    validate_post_enter_transition,
)


TRAIN_RECEIPT_SHA256 = "7be30e3930c31d9fb4ec4ebe2fffd1e8fce15bbf9f38ef06a05b720b6309ae1a"
TRAIN_RUNNER_SHA256 = "52309f42cc795705d70bd96555af8e50326419979ffbdb1b2f1cd21aefc7ea30"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def bound_file(root: Path, record: dict) -> bytes:
    value = record.get("private_path")
    if type(value) is not str:
        raise ValueError("Train frame path missing")
    path = (root / value).resolve()
    if (not path.is_relative_to(root.resolve()) or not path.is_file() or
            path.is_symlink()):
        raise ValueError("Train frame outside retained private source")
    raw = path.read_bytes()
    if digest(raw) != record.get("sha256"):
        raise ValueError("Train frame bytes changed")
    return raw


def inspect(*, external_root: Path) -> dict:
    output_root = (external_root / "work/native-desktop/gui-diagnostics/"
                   "v066-scoped-calc-writer-train-demo-20260928-001")
    receipt_path = output_root / "calc/receipt.json"
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    runner = (Path(__file__).resolve().parents[1] /
              "native_desktop_factory/v066_scoped_calc_writer_train_demo.py")
    if (digest(raw) != TRAIN_RECEIPT_SHA256 or
            digest(runner.read_bytes()) != TRAIN_RUNNER_SHA256 or
            receipt.get("demo_source_sha256") != TRAIN_RUNNER_SHA256 or
            receipt.get("split") != "train" or
            receipt.get("kind") != "calc" or
            receipt.get("status") != "train_gui_positive_passed" or
            len(receipt.get("normalized_actor_actions", [])) != 12):
        raise ValueError("Public-train Calc source and result changed")
    applied = receipt["normalized_actor_actions"]
    drifts = receipt.get("physical_frame_resamples", [])
    accepted = []
    for prior_step in (5, 7):
        prior = applied[prior_step]
        current = applied[prior_step + 1]
        matching = [row for row in drifts if row.get("step") == prior_step + 1]
        if (prior["normalized_action"].get("type") != "key" or
                prior["normalized_action"].get("key") != "Enter" or
                len(matching) != 1 or
                matching[0].get("frame_attempt") != 0 or
                current.get("step") != prior_step + 1 or
                current.get("status") != "applied" or
                current["normalized_action"].get("frame_id") is None or
                digest(current["normalized_action"]["frame_id"].encode()) !=
                    current.get("frame_id_sha256")):
            raise ValueError("Public-train Enter trajectory shape changed")
        drift = matching[0]
        old_obs, first_changed, fresh_obs, fresh_predispatch = (
            bound_file(output_root, item) for item in (
                drift["observed"], drift["changed"],
                current["observation"], current["predispatch"],
            )
        )
        value = validate_post_enter_transition(
            previous_action=prior["normalized_action"],
            first_observation=old_obs,
            first_predispatch=first_changed,
            fresh_observation=fresh_obs,
            fresh_predispatch=fresh_predispatch,
            waited_ms=1000,  # frozen runner requests time.sleep(1)
        )
        accepted.append(value)
    return {
        "schema": "cua-native-wdi-v066-post-enter-train-offline-candidate-v1",
        "status": "two_public_train_transitions_support_candidate_only",
        "source_scope": "public_train_calc_only",
        "private_train_receipt_sha256": TRAIN_RECEIPT_SHA256,
        "frozen_train_runner_sha256": TRAIN_RUNNER_SHA256,
        "material_transitions_checked": len(accepted),
        "material_transitions_settled_after_one_frozen_runner_retry":
            len(accepted),
        "requested_no_action_wait_ms": 1000,
        "wall_time_to_stability_measured": False,
        "fresh_observation_and_exact_predispatch_required": True,
        "stale_action_reuse_authorized": False,
        "selection_gui_transitions_measured": 0,
        "hidden_final_frames_used_for_candidate_design": False,
        "provider_creates": 0,
        "runtime_dispatch_authorized": False,
        "official_final_admissions": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    value = inspect(external_root=args.external_root)
    if args.public_out.exists() or args.public_out.is_symlink():
        raise ValueError("Exclusive public candidate evidence path required")
    args.public_out.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(args.public_out, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                         0o644)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps({"status": value["status"],
                      "public_sha256": digest(raw)}, sort_keys=True))


if __name__ == "__main__":
    main()
