"""Audit a quarantined four-edit PowerPoint-web development control.

The private input is an evaluator-owned provisional final family used to
calibrate Office baseline and GUI controls. A passing report grants no final
admission; its entire source family is excluded pending replacement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse
import zipfile

from ppt_wdi_factory import verify
from tools.audit_ppt_wdi_web_train_triad_v1 import semantic_source_equal


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_slides(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return sum(name.startswith("ppt/slides/slide") and name.endswith(".xml")
                   and name.removeprefix("ppt/slides/slide").removesuffix(".xml").isdigit()
                   for name in archive.namelist())


def write_new(path: Path, value: dict, *, private: bool) -> str:
    raw = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                 0o600 if private else 0o644)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staging-manifest", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--positive", type=Path, required=True)
    parser.add_argument("--near-miss", type=Path, required=True)
    parser.add_argument("--fresh-reset", type=Path, required=True)
    parser.add_argument("--invalid-one", type=Path, required=True)
    parser.add_argument("--invalid-two", type=Path, required=True)
    parser.add_argument("--invalid-one-receipt", type=Path, required=True)
    parser.add_argument("--invalid-two-receipt", type=Path, required=True)
    parser.add_argument("--cloud-items", type=Path, required=True)
    parser.add_argument("--private-out", type=Path, required=True)
    parser.add_argument("--public-out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.private_out.exists() and not args.public_out.exists(),
            "fresh output receipts required")
    manifest = json.loads(args.staging_manifest.read_bytes())
    quarantine = json.loads(args.quarantine.read_bytes())
    first = manifest["cases"][0]
    source = Path(first["source_path"])
    task = json.loads(source.with_name("task.private.json").read_bytes())
    family = first["source_group"]
    quarantined = [row for row in manifest["cases"] if row["source_group"] == family]
    require(task["split"] == "final_candidate" and
            task["task_id"] == first["task_id"] and
            set(quarantine["task_ids"]) == {row["task_id"] for row in quarantined} and
            len(quarantined) == 4 and quarantine["remaining_original_final_candidates"] == 96,
            "private four-task source-family quarantine changed")
    require(digest(source) == first["source_sha256"],
            "original source package changed")
    verify.freeze(source, task)
    source_equivalence = semantic_source_equal(source, args.baseline)
    oracle = verify.freeze(args.baseline, task, office_web_normalized=True)
    controls = {"positive": (args.positive, 1.0, 4),
                "near_miss": (args.near_miss, 0.0, 3),
                "fresh_reset": (args.fresh_reset, 0.0, 0)}
    checks = {}
    for label, (path, score, correct_count) in controls.items():
        result = verify.verify(args.baseline, path, oracle)
        require(result["status"] == "scored" and result["score"] == score and
                result["preservation_pass"] is True and
                not result["unexpected_parts"] and
                sum(row["correct"] for row in result["per_target"].values()) == correct_count and
                len(result["per_target"]) == 4,
                f"{label} downloaded saved-state control failed")
        checks[label] = {"download_sha256": digest(path), "score": score,
                         "correct_target_count": correct_count,
                         "preservation_pass": True}
    require(args.fresh_reset.read_bytes() == args.baseline.read_bytes(),
            "fresh attempt did not start from exact normalized baseline bytes")
    for label, path, receipt in (
        ("invalid_one", args.invalid_one, args.invalid_one_receipt),
        ("invalid_two", args.invalid_two, args.invalid_two_receipt),
    ):
        row = json.loads(receipt.read_bytes())
        require(count_slides(path) == 8 and row["observed_download_sha256"] == digest(path) and
                row["model_calls"] == 0 and row["scored_attempts"] == 0,
                f"{label} pre-action failure receipt changed")
    urls = json.loads(args.cloud_items.read_bytes())
    require(set(urls) == {"baseline", "positive", "near_miss", "fresh_reset",
                          "invalid_near_01", "invalid_near_02"} and
            len(set(urls.values())) == 6 and
            all(urlparse(url).scheme == "https" and
                urlparse(url).hostname == "onedrive.live.com" for url in urls.values()),
            "six distinct private OneDrive items required")
    url_hashes = {name: hashlib.sha256(url.encode()).hexdigest()
                  for name, url in urls.items()}
    private = {"schema": "envloop-ppt-wdi-web-final-development-private-v1",
               "status": "quarantined_family_development_control_not_final_admission",
               "task_id": task["task_id"], "source_group": family,
               "original_plan_sha256": manifest["plan_sha256"],
               "source_sha256": digest(source),
               "normalized_baseline_sha256": digest(args.baseline),
               "quarantine_receipt_sha256": digest(args.quarantine),
               "cloud_item_url_sha256": url_hashes,
               "source_equivalence": source_equivalence,
               "controls": checks,
               "pre_action_invalid_receipt_sha256": {
                   "first": digest(args.invalid_one_receipt),
                   "second": digest(args.invalid_two_receipt)},
               "quarantined_final_candidate_tasks": 4,
               "remaining_original_final_candidates": 96,
               "replacement_pending": 4,
               "model_calls": 0, "official_final_admitted": 0}
    private_sha = write_new(args.private_out, private, private=True)
    public = {"schema": "envloop-ppt-wdi-web-final-development-public-v1",
              "status": private["status"],
              "original_plan_sha256": manifest["plan_sha256"],
              "source_sha256": private["source_sha256"],
              "normalized_baseline_sha256": private["normalized_baseline_sha256"],
              "source_equivalence": source_equivalence,
              "control_scores": {key: {"score": row["score"],
                                       "correct_target_count": row["correct_target_count"],
                                       "preservation_pass": True}
                                 for key, row in checks.items()},
              "download_sha256": {key: row["download_sha256"]
                                  for key, row in checks.items()},
              "cloud_item_url_sha256": url_hashes,
              "pre_action_invalid_count": 2,
              "pre_action_invalid_receipt_sha256": private["pre_action_invalid_receipt_sha256"],
              "quarantine_receipt_sha256": private["quarantine_receipt_sha256"],
              "quarantined_source_families": 1,
              "quarantined_final_candidate_tasks": 4,
              "remaining_original_final_candidates": 96,
              "replacement_pending": 4,
              "private_receipt_sha256": private_sha,
              "model_calls": 0, "official_final_admitted": 0,
              "researcher_campaigns": 0}
    write_new(args.public_out, public, private=False)
    print(json.dumps({"status": public["status"],
                      "private_receipt_sha256": private_sha,
                      "official_final_admitted": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
