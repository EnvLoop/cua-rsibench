"""Bind one trusted neutral Impress save into a private candidate inventory.

Only metadata/geometry serialization may change: all slide text and drawable
kinds must remain identical before a fresh actor sandbox sees the candidate.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from . import factory as base
    from .verify import pptx_shape_structure, pptx_slide_shapes
else:
    import factory as base
    from verify import pptx_shape_structure, pptx_slide_shapes


def adopt(candidate_root: Path, task_id: str, normalization_dir: Path) -> dict:
    inventory_path = candidate_root / "candidate-inventory.json"
    inventory = json.loads(inventory_path.read_bytes())
    if inventory.get("design_revision") != "v2-distinct-structures":
        raise ValueError("Only the v2 candidate inventory is supported")
    rows = [r for r in inventory["tasks"] if r["task_id"] == task_id and r["split"] == "final_candidate"]
    if len(rows) != 1 or rows[0]["workflow"] != "impress-deck":
        raise ValueError("Unknown final Impress candidate")
    row = rows[0]
    directory = candidate_root / "final_candidate" / task_id
    artifact = directory / (task_id + ".pptx")
    original = artifact.read_bytes()
    if base.digest(original) != row["input_sha256"] or "normalization" in row:
        raise ValueError("Input already changed or normalized")
    neutral_raw = (normalization_dir / "receipt.json").read_bytes()
    neutral = json.loads(neutral_raw)
    normalized = (normalization_dir / "normalized.pptx").read_bytes()
    if neutral.get("status") != "neutral_save_observed" or neutral.get("kill_returned") is not True or neutral.get("is_running_after_kill") is not False:
        raise ValueError("Neutral native save did not complete and terminate")
    if neutral["original_sha256"] != base.digest(original) or neutral["normalized_sha256"] != base.digest(normalized):
        raise ValueError("Neutral saved bytes differ from receipt")
    if pptx_slide_shapes(original) != pptx_slide_shapes(normalized) or pptx_shape_structure(original) != pptx_shape_structure(normalized):
        raise ValueError("Neutral save changed slide content or drawable structure")
    artifact.write_bytes(normalized)
    oracle_path = directory / "oracle.json"
    oracle = json.loads(oracle_path.read_bytes())
    if oracle["input_sha256"] != neutral["original_sha256"]:
        raise ValueError("Oracle input differs from original")
    oracle["input_sha256"] = neutral["normalized_sha256"]
    oracle["normalization_receipt_sha256"] = base.digest(neutral_raw)
    oracle_path.write_bytes(base.json_bytes(oracle))
    row["input_sha256"] = base.digest(normalized)
    row["oracle_sha256"] = base.digest(oracle_path.read_bytes())
    row["normalization"] = {"original_sha256": neutral["original_sha256"],
                            "normalized_sha256": neutral["normalized_sha256"],
                            "receipt_sha256": base.digest(neutral_raw)}
    row["package_sha256"] = base.digest(base.json_bytes({k: v for k, v in row.items() if k != "package_sha256"}))
    (directory / "package.json").write_bytes(base.json_bytes(row))
    inventory.setdefault("normalization_receipts", {})[task_id] = row["normalization"]
    inventory_path.write_bytes(base.json_bytes(inventory))
    return {"task_id": task_id, "normalized_input_sha256": row["input_sha256"],
            "candidate_inventory_sha256": base.digest(inventory_path.read_bytes())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--normalization-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(adopt(args.candidate_root, args.task_id, args.normalization_dir), sort_keys=True))


if __name__ == "__main__":
    main()
