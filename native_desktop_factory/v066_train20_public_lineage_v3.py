"""Check the additive public hash correction for the train-only battery plan.

The dated v1 and v2 receipts are historical. A correction must bind their
actual public bytes and the unchanged full100 source freeze; it cannot silently
replace either receipt or infer a GUI/model result.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path


V1 = "docs/evidence/native-wdi-v066-train20-battery-preflight-amendment-2026-09-29.json"
V2 = "docs/evidence/native-wdi-v066-train20-battery-preflight-amendment-v2-2026-09-29.json"
PLAN = "docs/evidence/native-wdi-v066-train20-battery-authorized-plan-v2-2026-09-29.json"
FULL100 = "docs/evidence/native-wdi-v066-day-rollover-runtime-freeze-2026-09-29.json"
SCHEMA = "cua-native-wdi-v066-train20-battery-public-lineage-correction-v3"


def digest(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def build(*, source_root: Path, v1_path: Path,
          v2_path: Path, plan_path: Path,
          full100_freeze_path: Path) -> dict:
    paths = (v1_path, v2_path, plan_path, full100_freeze_path)
    if (tuple(path.name for path in paths) !=
            tuple(Path(name).name for name in (V1, V2, PLAN, FULL100)) or
            any(not path.is_file() or path.is_symlink() for path in paths)):
        raise ValueError("Exact public lineage files are required")
    v1_raw, v2_raw, plan_raw, full_raw = (path.read_bytes() for path in paths)
    v1, v2, plan, full = (json.loads(raw) for raw in
                          (v1_raw, v2_raw, plan_raw, full_raw))
    if (v1.get("schema") !=
            "cua-native-wdi-v066-train20-battery-preflight-amendment-public-v1" or
            v2.get("schema") !=
            "cua-native-wdi-v066-train20-battery-preflight-amendment-public-v2" or
            plan.get("schema") !=
            "cua-native-wdi-v066-train20-source-plan-public-v1" or
            full.get("schema") !=
            "cua-native-wdi-v066-day-rollover-runtime-freeze-public-v1" or
            v1.get("sft_candidate_count") != 15 or
            v1.get("holdout_candidate_count") != 5 or
            v2.get("sft_candidate_count") != 15 or
            v2.get("holdout_candidate_count") != 5 or
            plan.get("sft_candidate_count") != 15 or
            plan.get("holdout_candidate_count") != 5 or
            v1.get("assignment_unchanged") is not True or
            v2.get("assignment_unchanged") is not True or
            v2.get("new_plan_public_sha256") != digest(plan_raw) or
            v2.get("prior_offline_amendment_sha256") == digest(v1_raw) or
            any(value.get("official_final_admissions") != 0 or
                value.get("official_model_results") != 0
                for value in (v1, v2, plan, full)) or
            v1.get("e2b_train_guest_creates") != 0 or
            v1.get("tinker_calls") != 0 or
            v2.get("paid_train_e2b_creates") != 0 or
            v2.get("tinker_calls") != 0):
        raise ValueError("Published v1/v2 source lineage is not the pre-train correction")
    frozen = full.get("source_sha256s")
    if (type(frozen) is not dict or len(frozen) != 35 or
            any(digest((source_root / name).read_bytes()) != value
                for name, value in frozen.items())):
        raise ValueError("Running full100 source bytes differ from public freeze")
    return {
        "schema": SCHEMA,
        "status": "additive_public_hash_correction_before_any_train_call",
        "public_v1_path": V1,
        "public_v1_actual_sha256": digest(v1_raw),
        "published_v2_path": V2,
        "published_v2_sha256": digest(v2_raw),
        "supersedes_published_v2_sha256": digest(v2_raw),
        "v2_stale_prior_v1_sha256_preserved":
            v2["prior_offline_amendment_sha256"],
        "v2_plan_path": PLAN,
        "v2_plan_sha256": digest(plan_raw),
        "full100_public_freeze_path": FULL100,
        "full100_public_freeze_sha256": digest(full_raw),
        "full100_frozen_source_count": 35,
        "validator_source_sha256": digest(Path(__file__).read_bytes()),
        "sft_candidate_count": 15,
        "holdout_candidate_count": 5,
        "task_assignment_unchanged": True,
        "paid_train_guest_creates": 0,
        "tinker_calls": 0,
        "official_final_admissions": 0,
        "official_model_results": 0,
    }


def validate(*, correction_path: Path, **kwargs) -> dict:
    if not correction_path.is_file() or correction_path.is_symlink():
        raise ValueError("Additive public correction is absent")
    value = json.loads(correction_path.read_bytes())
    expected = build(**kwargs)
    if value != expected:
        raise ValueError("Public train battery hash correction drifted")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--v1", type=Path, required=True)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--full100-freeze", type=Path, required=True)
    parser.add_argument("--correction", type=Path, required=True)
    args = parser.parse_args()
    result = validate(
        correction_path=args.correction, source_root=args.source_root,
        v1_path=args.v1, v2_path=args.v2, plan_path=args.plan,
        full100_freeze_path=args.full100_freeze)
    print(json.dumps({"status": result["status"],
                      "public_v1_actual_sha256": result[
                          "public_v1_actual_sha256"],
                      "published_v2_sha256": result[
                          "published_v2_sha256"],
                      "official_final_admissions": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
