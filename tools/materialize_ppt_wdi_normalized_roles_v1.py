"""Create three exact PPT attempt copies after trusted Office baseline freeze.

This is private evaluator setup. The source and downloaded Office-saved
baseline are independently checked before any role file is written. No GUI
attempt or final-task admission is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


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
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--index", type=int, required=True)
    parser.add_argument("--normalized-baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    private = (Path.cwd() / "work").resolve()
    manifest_path, out = args.manifest.resolve(), args.out.resolve()
    require(manifest_path.is_relative_to(private) and
            out.is_relative_to(private) and not out.exists(),
            "private manifest and new work/ receipt required")
    manifest = json.loads(manifest_path.read_bytes())
    require(manifest["schema"] == "envloop-ppt-wdi-web-final-gui-staging-private-v2" and
            manifest["case_count"] == 100 and
            0 <= args.index < 100,
            "100-case baseline staging manifest changed")
    case = manifest["cases"][args.index]
    require(case["index"] == args.index and len(case["targets"]) == 4,
            "case index or four target fields changed")
    source = Path(case["source_path"])
    source_raw = source.read_bytes()
    require(sha(source_raw) == case["source_sha256"] and
            Path(case["copies"]["baseline"]).read_bytes() == source_raw,
            "original local source baseline changed")
    task = json.loads(source.with_name("task.private.json").read_bytes())
    require(task["task_id"] == case["task_id"],
            "private task package differs from staging case")
    verify.freeze(source, task)
    baseline_raw = args.normalized_baseline.read_bytes()
    require(sha(baseline_raw) != case["source_sha256"],
            "trusted Office baseline save was not observed")
    verify.freeze(args.normalized_baseline, task, office_web_normalized=True)
    source_equivalence = semantic_source_equal(source, args.normalized_baseline)
    roles = {}
    for role in ("positive", "near_miss", "fresh_reset"):
        target = Path(case["copies"][role]).resolve()
        require(target.is_relative_to(manifest_path.parent) and not target.exists(),
                "normalized role copy already exists or left private staging")
        write_new(target, baseline_raw)
        roles[role] = {"path": str(target), "sha256": sha(target.read_bytes())}
    require(len({row["sha256"] for row in roles.values()}) == 1 and
            next(iter(roles.values()))["sha256"] == sha(baseline_raw),
            "role copies differ from frozen Office baseline")
    receipt = {"schema": "envloop-ppt-wdi-normalized-roles-private-v1",
               "index": args.index, "task_id": case["task_id"],
               "source_sha256": case["source_sha256"],
               "normalized_baseline_sha256": sha(baseline_raw),
               "source_equivalence": source_equivalence,
               "roles": roles, "model_calls": 0,
               "official_final_admitted": 0}
    receipt_raw = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    write_new(out, receipt_raw)
    print(json.dumps({"status": "three_exact_normalized_attempt_copies_staged",
                      "case_index": args.index, "copy_count": 3,
                      "baseline_sha256": sha(baseline_raw),
                      "private_receipt_sha256": sha(receipt_raw),
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
