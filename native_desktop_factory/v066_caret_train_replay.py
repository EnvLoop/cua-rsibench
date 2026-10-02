"""Read-only, train-only replay of Desktop v0.6.6 raw drift pairs.

This is shape calibration, not a live E2B or final-model attempt. It never
opens selection/final traces and emits aggregate counts without task IDs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import qwen_v066_adapter
from .v066_final_freeze import digest


def replay_train_shape(trace_root: Path) -> dict:
    counts = {"train_attempts": 0, "train_drift_pairs": 0,
              "narrow_caret_shape_pairs": 0,
              "material_or_other_pairs_rejected": 0,
              "missing_or_changed_raw_pairs": 0}
    directories = sorted(trace_root.glob("v066-train-primitive-smoke-*"))
    if not directories:
        raise ValueError("No explicitly named v0.6.6 train traces found")
    for directory in directories:
        receipt_path = directory / "receipt.json"
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise ValueError("A named train trace lacks its receipt")
        receipt = json.loads(receipt_path.read_bytes())
        if (receipt.get("schema") !=
                "cua-native-wdi-gui-development-attempt-v1" or
                receipt.get("split") != "train" or
                receipt.get("purpose") !=
                "v066_public_train_primitive_smoke_no_model" or
                receipt.get("official_final_model_attempts") != 0):
            raise ValueError("Replay refuses non-train or model trace")
        counts["train_attempts"] += 1
        for row in receipt.get("physical_frame_resamples", []):
            step, attempt = row.get("step"), row.get("frame_attempt")
            if (type(step) is not int or step < 0 or
                    type(attempt) is not int or not 0 <= attempt < 5):
                raise ValueError("Train drift index changed")
            observed_path = directory / f"frame-{step:02d}-{attempt}.png"
            changed_path = directory / f"drift-{step:02d}-{attempt}.png"
            if (not observed_path.is_file() or observed_path.is_symlink() or
                    not changed_path.is_file() or changed_path.is_symlink()):
                counts["missing_or_changed_raw_pairs"] += 1
                continue
            observed = observed_path.read_bytes()
            changed = changed_path.read_bytes()
            if (digest(observed) != row.get("observation_screenshot_sha256") or
                    digest(changed) != row.get("changed_screenshot_sha256")):
                counts["missing_or_changed_raw_pairs"] += 1
                continue
            counts["train_drift_pairs"] += 1
            if qwen_v066_adapter._single_caret_column(observed, changed):
                counts["narrow_caret_shape_pairs"] += 1
            else:
                counts["material_or_other_pairs_rejected"] += 1
    if counts["missing_or_changed_raw_pairs"]:
        raise ValueError("Train raw screenshot evidence incomplete")
    return {"schema": "cua-native-wdi-v066-caret-train-shape-replay-v1",
            "scope": "train_only_no_provider_no_model",
            "adapter_sha256": digest(Path(qwen_v066_adapter.__file__).read_bytes()),
            **counts,
            "live_two_state_return_verified": False,
            "official_final_model_results": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(replay_train_shape(args.trace_root),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
