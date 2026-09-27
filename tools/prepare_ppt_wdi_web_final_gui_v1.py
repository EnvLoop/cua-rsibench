"""Stage evaluator-private PowerPoint-web baselines for 100 final candidates.

Only the raw baseline copy is materialized per case. The other three role
paths are reserved until a trusted Office-saved baseline can be frozen and
copied byte-for-byte. This does not upload, score, or admit a final task.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from ppt_wdi_factory import verify


ROLES = ("baseline", "positive", "near_miss", "fresh_reset")
SLIDES = {"summary": 1, "ledger": 4, "interpretation": 5,
          "decision": 6, "attribution": 7,
          "chart_caption": 3,
          "legend_cpi": 3, "legend_unemployment": 3}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write_new(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--packages", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to((Path.cwd() / "work").resolve()) and
            not out.exists(), "fresh ignored work/ output required")
    raw_plan = args.plan.read_bytes()
    require(sha(raw_plan) == args.plan_sha256, "private plan hash changed")
    plan = json.loads(raw_plan)
    require(plan["schema"] == "ppt-wdi-original-candidates-v1" and
            {key: len(rows) for key, rows in plan["sets"].items()} ==
            {"train": 20, "selection": 20, "final_candidate": 100},
            "20/20/100 original inventory changed")
    finals = plan["sets"]["final_candidate"]
    require(len({row["task_id"] for row in finals}) == 100 and
            len({row["source_group"] for row in finals}) == 25 and
            set(Counter(row["workflow"] for row in finals).values()) == {10},
            "final identity, family, or workflow balance changed")
    source_sets = [{row["source_group"] for row in plan["sets"][split]}
                   for split in ("train", "selection", "final_candidate")]
    require(not (source_sets[0] & source_sets[1] or
                 source_sets[0] & source_sets[2] or
                 source_sets[1] & source_sets[2]),
            "source-family split overlaps")
    out.mkdir(parents=True, mode=0o700)
    cases = []
    for index, row in enumerate(finals):
        package = args.packages / "final_candidate" / row["task_id"]
        source = package / "source.pptx"
        private_task = package / "task.private.json"
        require(json.loads(private_task.read_bytes()) == row,
                "task package differs from frozen plan")
        frozen = verify.freeze(source, row)
        require(len(frozen["targets"]) == 4,
                "final source lacks four independent target fields")
        source_raw = source.read_bytes()
        case_dir = out / f"case-{index:03d}"
        case_dir.mkdir(mode=0o700)
        copies = {}
        for role in ROLES:
            filename = f"EL-PPT-Final-{index+1:03d}-{role.replace('_', '-')}.pptx"
            target = case_dir / filename
            if role == "baseline":
                write_new(target, source_raw)
            copies[role] = str(target)
        cases.append({
            "index": index, "task_id": row["task_id"],
            "source_group": row["source_group"],
            "workflow": row["workflow"],
            "source_path": str(source.resolve()),
            "source_sha256": sha(source_raw),
            "package_task_sha256": sha(private_task.read_bytes()),
            "copies": copies,
            "targets": [{"key": key, "slide": SLIDES[key],
                         "draft": row["draft"][key],
                         "correct": row["correct"][key]}
                        for key in row["target_keys"]],
            "near_miss_omits": row["target_keys"][0],
        })
    document = {"schema": "envloop-ppt-wdi-web-final-gui-staging-private-v2",
                "status": "raw_baselines_only_normalized_roles_pending",
                "plan_sha256": args.plan_sha256,
                "case_count": 100, "roles_per_case": list(ROLES),
                "baseline_upload_copies": 100,
                "pending_normalized_role_copies": 300,
                "official_final_admitted": 0,
                "model_calls": 0,
                "cases": cases}
    raw = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
    write_new(out / "manifest.private.json", raw)
    print(json.dumps({"status": document["status"],
                      "case_count": 100, "baseline_upload_copies": 100,
                      "pending_normalized_role_copies": 300,
                      "workflow_count": 10, "source_family_count": 25,
                      "private_manifest_sha256": sha(raw),
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
